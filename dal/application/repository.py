"""Read-only access to an immutable compiler query bundle."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from pathlib import Path

import duckdb

from dal.database import read_only_connection

from .models import CatalogObject, EvidenceSummary


class BundleNotFoundError(FileNotFoundError):
    pass


class BundleCatalog:
    def __init__(self, bundle: Path | str):
        candidate = Path(bundle)
        self.root = candidate
        revision = None
        if candidate.is_dir() and (candidate / "active.json").is_file():
            active = _json((candidate / "active.json").read_text())
            revision = active.get("revision")
            if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{24}", revision):
                raise ValueError("invalid active bundle revision")
            candidate = candidate / "revisions" / revision
        self.database = candidate if candidate.suffix == ".duckdb" else candidate / "catalog.duckdb"
        self.manifest = None if candidate.suffix == ".duckdb" else candidate / "manifest.json"
        if not self.database.is_file():
            raise BundleNotFoundError(f"compiled bundle not found: {self.database}")
        try:
            self._validate_metadata(revision)
        except (OSError, duckdb.Error, KeyError, json.JSONDecodeError) as error:
            raise ValueError(f"compiled bundle metadata is corrupt: {error}") from error

    def snapshot(self) -> "BundleCatalog":
        """Resolve activation once; all reads in an operation use that revision."""
        return BundleCatalog(self.root)

    def _validate_metadata(self, revision):
        from dal.compiler.constants import BUNDLE_FORMAT, COMPILER_VERSION

        manifest = _json(self.manifest.read_text()) if self.manifest else None
        if manifest is not None:
            if (manifest.get("format") != BUNDLE_FORMAT or manifest.get("compiler_version") != COMPILER_VERSION
                    or (revision is not None and manifest.get("revision") != revision)):
                raise ValueError("bundle metadata does not match the active revision or compiler")
        with self._open() as connection:
            if manifest is not None:
                row = connection.execute("SELECT value FROM meta WHERE key = 'revision'").fetchone()
                if row is None or row[0] != manifest.get("revision"):
                    raise ValueError("database revision does not match bundle metadata")
            for table in ("objects", "links", "terms", "evidence", "embeddings", "bm25_terms", "bm25_corpus"):
                connection.execute(f"SELECT * FROM {table} LIMIT 0")

    def embedding_health(self) -> dict[str, object]:
        if self.manifest and self.manifest.is_file():
            document = _json(self.manifest.read_text())
            health = document.get("health")
            if isinstance(health, dict) and isinstance(health.get("embeddings"), dict):
                return health["embeddings"]
        with self._open() as connection:
            if not _has_table(connection, "meta"):
                return {"status": "unavailable", "reason": "embedding_metadata_missing"}
            row = connection.execute(
                "SELECT value FROM meta WHERE key = 'embedding_health'"
            ).fetchone()
        return (_json(row[0]) if row else
                {"status": "unavailable", "reason": "embedding_metadata_missing"})

    def list_objects(self, kind: str, limit: int, offset: int, include_deprecated: bool = False) -> tuple[CatalogObject, ...]:
        with self._open() as connection:
            rows = connection.execute(
                "SELECT id, kind, name, parent_id, source, payload FROM objects "
                "WHERE kind = ? AND (? OR coalesce(json_extract_string(payload, '$.status'), 'published') != 'deprecated') "
                "ORDER BY lower(name), id LIMIT ? OFFSET ?",
                [kind, include_deprecated, limit, offset],
            ).fetchall()
        return tuple(_object(row) for row in rows)

    def get_object(self, object_id: str, kind: str | None = None) -> CatalogObject | None:
        condition = "id = ?" + (" AND kind = ?" if kind else "")
        parameters = [object_id, *([kind] if kind else [])]
        with self._open() as connection:
            row = connection.execute(
                "SELECT id, kind, name, parent_id, source, payload FROM objects WHERE " + condition,
                parameters,
            ).fetchone()
        return _object(row) if row else None

    def bm25(self, terms: tuple[str, ...], limit: int, kind: str | None) -> dict[str, float]:
        if not terms:
            return {}
        kind_clause = " AND o.kind = ?" if kind else ""
        parameters: list[object] = [list(terms)]
        if kind:
            parameters.append(kind)
        with self._open() as connection:
            rows = connection.execute(
                "SELECT t.object_id, t.frequency, b.document_frequency, c.document_count, "
                "c.average_document_length, lengths.length FROM terms t "
                "JOIN objects o ON o.id = t.object_id "
                "JOIN bm25_terms b USING (term) CROSS JOIN bm25_corpus c "
                "JOIN (SELECT object_id, sum(frequency) length FROM terms GROUP BY object_id) "
                "lengths ON lengths.object_id = t.object_id "
                "WHERE t.term IN (SELECT UNNEST(?))" + kind_clause,
                parameters,
            ).fetchall()
        scores: dict[str, float] = {}
        for object_id, frequency, document_frequency, count, average, length in rows:
            saturation = frequency * 2.2 / (
                frequency + 1.2 * (0.25 + 0.75 * length / max(average, 1.0))
            )
            inverse_frequency = math.log(1.0 + (count - document_frequency + 0.5) /
                                         (document_frequency + 0.5))
            scores[object_id] = scores.get(object_id, 0.0) + inverse_frequency * saturation
        return dict(sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit])

    def objects(self, object_ids: Iterable[str]) -> dict[str, CatalogObject]:
        identifiers = tuple(dict.fromkeys(object_ids))
        if not identifiers:
            return {}
        with self._open() as connection:
            rows = connection.execute(
                "SELECT id, kind, name, parent_id, source, payload FROM objects "
                "WHERE id IN (SELECT UNNEST(?))", [list(identifiers)],
            ).fetchall()
        return {item.id: item for item in map(_object, rows)}

    def embedding_index(
        self, kind: str | None = None,
    ) -> tuple[dict[str, tuple[float, ...]], str]:
        kind_clause = " WHERE o.kind = ?" if kind else ""
        parameters = [kind] if kind else []
        with self._open() as connection:
            if not _has_table(connection, "embeddings"):
                return {}, "missing"
            rows = connection.execute(
                "SELECT e.object_id, e.vector FROM embeddings e "
                "JOIN objects o ON o.id = e.object_id" + kind_clause, parameters,
            ).fetchall()
        vectors = {
            object_id: tuple(float(value) for value in vector) for object_id, vector in rows
        }
        return vectors, "available" if vectors else "empty"

    def degrees(self, object_ids: Iterable[str]) -> dict[str, int]:
        identifiers = tuple(object_ids)
        if not identifiers:
            return {}
        with self._open() as connection:
            rows = connection.execute(
                "SELECT object_id, count(*) FROM ("
                "SELECT source_id object_id FROM links UNION ALL SELECT target_id FROM links) "
                "WHERE object_id IN (SELECT UNNEST(?)) GROUP BY object_id",
                [list(identifiers)],
            ).fetchall()
        return dict(rows)

    def evidence_strengths(self, object_ids: Iterable[str]) -> dict[str, float]:
        identifiers = tuple(object_ids)
        if not identifiers:
            return {}
        with self._open() as connection:
            rows = connection.execute(
                "SELECT subject_id, payload FROM evidence "
                "WHERE subject_id IN (SELECT UNNEST(?))", [list(identifiers)],
            ).fetchall()
        result: dict[str, float] = {}
        for subject_id, payload in rows:
            strength = _json(payload).get("strength")
            if isinstance(strength, (int, float)):
                result[subject_id] = max(result.get(subject_id, 0.0), float(strength))
        return result


    def evidence(self, object_ids: Iterable[str], limit: int) -> tuple[EvidenceSummary, ...]:
        identifiers = tuple(object_ids)
        if not identifiers or limit == 0:
            return ()
        with self._open() as connection:
            rows = connection.execute(
                "SELECT id, layer, subject_id, claim_path, source_kind, payload FROM evidence "
                "WHERE subject_id IN (SELECT UNNEST(?)) ORDER BY layer, id LIMIT ?",
                [list(identifiers), limit],
            ).fetchall()
        result = []
        for row in rows:
            value = _json(row[5])
            source = value.get("source", {})
            result.append(EvidenceSummary(
                *row[:5], value.get("strength"), value.get("claim_value"),
                value.get("collected_at"), source.get("revision"),
                value.get("content"), value.get("measurement"),
            ))
        return tuple(result)

    def _open(self):
        return read_only_connection(self.database)


def _object(row) -> CatalogObject:
    return CatalogObject(*row[:5], _json(row[5]))


def _json(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else json.loads(str(value))


def _has_table(connection, name: str) -> bool:
    return connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name],
    ).fetchone()[0] > 0
