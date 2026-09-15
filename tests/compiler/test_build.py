"""Incremental builds preserve source files and activate verified artifacts."""

from copy import deepcopy
import json

import duckdb
import pytest

from dal.compiler import BundleBuilder, CompilationError
from dal.evidence import serialize_snapshot

from .fixtures import native_document


def test_idempotent_build_preserves_document_and_search_indexes(tmp_path):
    document = native_document()
    original = deepcopy(document)
    builder = BundleBuilder(tmp_path / "bundle")
    first = builder.build(document)
    second = builder.build(document)
    assert document == original
    assert not first.reused and second.reused
    assert first.bundle == second.bundle
    assert first.revision == json.loads((builder.root / "active.json").read_text())["revision"]
    with duckdb.connect(str(first.bundle / "catalog.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM objects").fetchone()[0] == len(document["objects"])
        assert db.execute("SELECT count(*) FROM links WHERE kind='contains'").fetchone()[0] == 5
        assert db.execute("SELECT document_count FROM bm25_corpus").fetchone()[0] == len(document["objects"])
        assert db.execute("SELECT count(*) FROM bm25_terms").fetchone()[0] > 0
        assert db.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 0
    manifest = json.loads((first.bundle / "manifest.json").read_text())
    assert manifest["health"]["embeddings"]["status"] == "unavailable"


def test_existing_evidence_snapshot_has_same_revision_as_records(tmp_path):
    snapshot = tmp_path / "evidence.json"
    snapshot.write_bytes(serialize_snapshot(()))
    builder = BundleBuilder(tmp_path / "bundle")
    first = builder.build(native_document(), ())
    second = builder.build(native_document(), snapshot)
    assert second.reused and first.revision == second.revision


def test_changed_document_reuses_unchanged_rows_and_removes_deleted_objects(tmp_path):
    document = native_document()
    builder = BundleBuilder(tmp_path / "bundle")
    first = builder.build(document)
    with duckdb.connect(str(first.bundle / "catalog.duckdb"), read_only=True) as db:
        hashes = dict(db.execute("SELECT id, content_hash FROM objects").fetchall())
    document["objects"][0]["description"] = "Changed sales description"
    document["objects"] = [obj for obj in document["objects"] if obj["kind"] != "metric"]
    second = builder.build(document)
    assert second.revision != first.revision
    assert (second.changed_objects, second.removed_objects) == (1, 1)
    with duckdb.connect(str(second.bundle / "catalog.duckdb"), read_only=True) as db:
        updated = dict(db.execute("SELECT id, content_hash FROM objects").fetchall())
        assert "metric:orders" not in updated
        assert sum(hashes[key] == digest for key, digest in updated.items()) == len(updated) - 1
        assert db.execute("SELECT count(*) FROM links WHERE source_id='metric:orders'").fetchone()[0] == 0


def test_invalid_reference_cannot_replace_active_revision(tmp_path):
    builder = BundleBuilder(tmp_path / "bundle")
    first = builder.build(native_document())
    invalid = native_document()
    next(obj for obj in invalid["objects"] if obj["kind"] == "join")["right"] = ["missing"]
    with pytest.raises(CompilationError, match="reference does not resolve"):
        builder.build(invalid)
    assert json.loads((builder.root / "active.json").read_text())["revision"] == first.revision


@pytest.mark.parametrize("filename", ["catalog.duckdb", "evidence.json"])
def test_missing_cached_artifact_is_rejected_before_activation(tmp_path, filename):
    builder = BundleBuilder(tmp_path / "bundle")
    cached = builder.build(native_document())
    changed = native_document()
    changed["objects"][0]["description"] = "New revision"
    current = builder.build(changed)
    (cached.bundle / filename).unlink()
    with pytest.raises(ValueError):
        builder.build(native_document())
    assert json.loads((builder.root / "active.json").read_text())["revision"] == current.revision


def test_corrupted_cached_artifact_is_rejected(tmp_path):
    builder = BundleBuilder(tmp_path / "bundle")
    result = builder.build(native_document())
    (result.bundle / "evidence.json").write_bytes(b"[]")
    with pytest.raises(ValueError, match="checksum"):
        builder.build(native_document())
