"""DuckDB writer for immutable compiled query bundles."""

from __future__ import annotations

import json
import math
import re
import tempfile
from collections import Counter
from collections.abc import Iterable

import duckdb

from .evidence_reader import snapshot_records
from .model import CompiledLink, CompiledObject

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS objects (id VARCHAR PRIMARY KEY, kind VARCHAR, name VARCHAR, "
    "parent_id VARCHAR, source VARCHAR, search_text VARCHAR, payload JSON, content_hash VARCHAR)",
    "CREATE TABLE IF NOT EXISTS links (id VARCHAR PRIMARY KEY, kind VARCHAR, source_id VARCHAR, "
    "target_id VARCHAR, payload JSON)",
    "CREATE TABLE IF NOT EXISTS terms (object_id VARCHAR, term VARCHAR, frequency INTEGER)",
    "CREATE TABLE IF NOT EXISTS bm25_terms (term VARCHAR PRIMARY KEY, "
    "document_frequency BIGINT, collection_frequency BIGINT)",
    "CREATE TABLE IF NOT EXISTS bm25_corpus (document_count BIGINT, "
    "average_document_length DOUBLE)",
    "CREATE TABLE IF NOT EXISTS embeddings (object_id VARCHAR PRIMARY KEY, vector FLOAT[])",
    "CREATE TABLE IF NOT EXISTS evidence (id VARCHAR PRIMARY KEY, layer VARCHAR, subject_id VARCHAR, "
    "claim_path VARCHAR, source_kind VARCHAR, payload JSON)",
    "CREATE TABLE IF NOT EXISTS meta (key VARCHAR PRIMARY KEY, value VARCHAR)",
    "CREATE INDEX IF NOT EXISTS terms_term_idx ON terms(term)",
    "CREATE INDEX IF NOT EXISTS links_source_idx ON links(source_id)",
    "CREATE INDEX IF NOT EXISTS links_target_idx ON links(target_id)",
)


def open_writer(path) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(str(path))
    for statement in SCHEMA:
        connection.execute(statement)
    return connection


def update_objects(
    connection: duckdb.DuckDBPyConnection, objects: Iterable[CompiledObject],
    hashes: dict[str, str], changed: set[str], removed: set[str],
) -> None:
    affected = sorted(changed | removed)
    if affected:
        connection.execute("DELETE FROM terms WHERE object_id IN (SELECT UNNEST(?))", [affected])
        connection.execute("DELETE FROM objects WHERE id IN (SELECT UNNEST(?))", [affected])
    for item in objects:
        if item.object_id not in changed:
            continue
        connection.execute(
            "INSERT INTO objects VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [item.object_id, item.kind, item.name, item.parent_id, item.source,
             item.search_text, item.payload, hashes[item.object_id]],
        )
        frequencies = Counter(_tokens(item.search_text))
        connection.executemany(
            "INSERT INTO terms VALUES (?, ?, ?)",
            [(item.object_id, term, count) for term, count in frequencies.items()],
        )
    if affected:
        refresh_bm25_statistics(connection)


def refresh_bm25_statistics(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("DELETE FROM bm25_terms")
    connection.execute(
        "INSERT INTO bm25_terms "
        "SELECT term, count(*), sum(frequency) FROM terms GROUP BY term"
    )
    connection.execute("DELETE FROM bm25_corpus")
    connection.execute(
        "INSERT INTO bm25_corpus "
        "SELECT count(*), coalesce(avg(coalesce(length, 0)), 0) FROM objects "
        "LEFT JOIN (SELECT object_id, sum(frequency) AS length FROM terms GROUP BY object_id) "
        "ON objects.id = object_id"
    )


def replace_links(connection, links: Iterable[CompiledLink]) -> None:
    connection.execute("DELETE FROM links")
    rows = [
        (item.link_id, item.kind, item.source_id, item.target_id, item.payload)
        for item in links
    ]
    if rows:
        connection.executemany("INSERT INTO links VALUES (?, ?, ?, ?, ?)", rows)


def update_embeddings(
    connection: duckdb.DuckDBPyConnection,
    objects: Iterable[CompiledObject],
    changed: set[str],
    removed: set[str],
    embedder,
    rebuild: bool,
) -> None:
    materialized = tuple(objects)
    if embedder is None:
        connection.execute("DELETE FROM embeddings")
        return
    if not isinstance(embedder.dimensions, int) or embedder.dimensions <= 0:
        raise ValueError("embedder dimensions must be a positive integer")
    selected = materialized if rebuild else tuple(
        item for item in materialized if item.object_id in changed
    )
    affected = sorted(
        ({item.object_id for item in materialized} if rebuild else changed) | removed
    )
    if affected:
        connection.execute(
            "DELETE FROM embeddings WHERE object_id IN (SELECT UNNEST(?))", [affected],
        )
    if not selected:
        return
    vectors = tuple(embedder.embed(tuple(item.search_text for item in selected)))
    if len(vectors) != len(selected):
        raise ValueError("embedder returned the wrong number of vectors")
    rows = []
    for item, vector in zip(selected, vectors):
        values = tuple(float(value) for value in vector)
        if len(values) != embedder.dimensions:
            raise ValueError("embedder returned a vector with the wrong dimensions")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("embedder returned a nonfinite vector")
        rows.append((item.object_id, values))
    connection.executemany("INSERT INTO embeddings VALUES (?, ?)", rows)


def replace_evidence(connection, snapshot) -> int:
    connection.execute("DELETE FROM evidence")
    lines = _evidence_json_lines(snapshot)
    try:
        if lines.stat().st_size == 0:
            return 0
        connection.execute(
            "INSERT INTO evidence "
            "SELECT record_id, layer, subject_id, claim_path, source.kind, to_json(records) "
            "FROM read_json_auto(?, format = 'newline_delimited') AS records",
            [str(lines)],
        )
        return connection.execute("SELECT count(*) FROM evidence").fetchone()[0]
    finally:
        lines.unlink(missing_ok=True)


def _evidence_json_lines(snapshot):
    descriptor, name = tempfile.mkstemp(
        prefix=".evidence-records-", suffix=".jsonl", dir=snapshot.parent,
    )
    target = type(snapshot)(name)
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as stream:
            for item in snapshot_records(snapshot):
                json.dump(item, stream, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                stream.write("\n")
        return target
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def set_meta(connection, values: dict[str, str]) -> None:
    for key, value in values.items():
        connection.execute("DELETE FROM meta WHERE key = ?", [key])
        connection.execute("INSERT INTO meta VALUES (?, ?)", [key, value])


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1]
