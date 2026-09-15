"""Read-only import of the attached Legacy analyst archive."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from dal.evidence import LegacyEvidenceExtractor, SourceKind
from dal.collectors.types import claim

from .catalog import LegacyCatalogImporter, CatalogImport, ImportDiagnostic
from .semantic import enrich_document


class LegacyArchiveImporter:
    def __init__(self, archive: Path | str):
        self.archive = Path(archive)

    def convert(self, model_name: str, *, include_evidence: bool = False) -> CatalogImport:
        with zipfile.ZipFile(self.archive) as source, tempfile.TemporaryDirectory(
            prefix="dal-legacy-import-",
        ) as temporary:
            database = Path(temporary) / "context_graph.duckdb"
            with (
                source.open(_member(source, "assets/context_graph.duckdb")) as incoming,
                database.open("wb") as outgoing,
            ):
                shutil.copyfileobj(incoming, outgoing)
            revision = "sha256:" + hashlib.sha256(self.archive.read_bytes()).hexdigest()
            # ZIP member time is stable across imports, unlike the invocation time.
            member = source.getinfo(_member(source, "assets/context_graph.duckdb"))
            collected_at = datetime(*member.date_time, tzinfo=timezone.utc)
            evidence = LegacyEvidenceExtractor(database, revision, collected_at).records() if include_evidence else ()
            result = LegacyCatalogImporter(database).convert(model_name, evidence)
            questions = _json(source, "assets/semantic/curated_questions.json")
            document = enrich_document(
                result.document,
                model_name=model_name,
                entity_definitions=_json(source, "assets/semantic/entity_definitions.json"),
                relation_names=_json(source, "assets/semantic/relation_names.json"),
                curated_questions=questions,
                query_cookbook=_text(source, "references/query-cookbook.md", required=False),
                source_revision=revision,
            )
            omitted = tuple({"source_table": "curated_questions", "source_id": key, **value}
                            for key, value in questions.items() if isinstance(value, dict) and value.get("speculative"))
            diagnostics = result.diagnostics
            if omitted:
                diagnostics += (ImportDiagnostic("REVIEW_REQUIRED", "curated_questions",
                                f"{len(omitted)} questions explicitly marked speculative retained for review, not published."),)
            evidence_records = result.evidence
            if include_evidence:
                evidence_records += tuple(claim(
                    item["id"], "/curation", item, kind=SourceKind.CURATION,
                    revision=revision, collected_at=collected_at, uri=f"legacy-archive:{revision}#{item['id']}",
                ) for item in document["objects"] if item["kind"] in {"entity", "relation", "doctrine", "gold_query"})
            return CatalogImport(
                document=document, tables=result.tables, fields=result.fields,
                relationships=result.relationships, diagnostics=diagnostics,
                evidence=evidence_records,
                omitted_records=result.omitted_records + omitted,
            )


def _json(source: zipfile.ZipFile, suffix: str) -> dict[str, object]:
    value = json.loads(_text(source, suffix))
    if not isinstance(value, dict):
        raise ValueError(f"archive asset must be an object: {suffix}")
    return value


def _text(source: zipfile.ZipFile, suffix: str, *, required: bool = True) -> str | None:
    try:
        name = _member(source, suffix)
    except ValueError:
        if not required:
            return None
        raise
    return source.read(name).decode("utf-8")


def _member(source: zipfile.ZipFile, suffix: str) -> str:
    matches = [name for name in source.namelist() if name.endswith("/" + suffix)]
    if len(matches) != 1:
        raise ValueError(f"archive must contain exactly one {suffix}")
    return matches[0]
