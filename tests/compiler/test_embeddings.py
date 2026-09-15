"""Optional local embedding index contracts."""

import json

import duckdb
import pytest

from dal.compiler import BundleBuilder

from .fixtures import native_document


class DeterministicEmbedder:
    provider = "test"
    model_id = "deterministic-v1"
    dimensions = 3

    def __init__(self):
        self.batches = []

    def embed(self, texts):
        self.batches.append(tuple(texts))
        return [
            (float(len(text)), float(text.count("sales")), 1.0)
            for text in texts
        ]


def test_injected_embedder_builds_real_local_vectors(tmp_path):
    embedder = DeterministicEmbedder()
    result = BundleBuilder(tmp_path / "bundle", embedder).build(native_document())

    connection = duckdb.connect(str(result.bundle / "catalog.duckdb"), read_only=True)
    try:
        rows = connection.execute(
            "SELECT object_id, vector FROM embeddings ORDER BY object_id"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == len(native_document()["objects"])
    assert all(len(vector) == 3 for _, vector in rows)
    manifest = json.loads((result.bundle / "manifest.json").read_text())
    assert manifest["health"]["embeddings"] == {
        "status": "available", "provider": "test",
        "model": "deterministic-v1", "dimensions": 3,
    }


def test_incremental_build_embeds_only_changed_objects(tmp_path):
    embedder = DeterministicEmbedder()
    builder = BundleBuilder(tmp_path / "bundle", embedder)
    document = native_document()
    builder.build(document)
    document["objects"][0]["description"] = "Changed sales description"

    result = builder.build(document)

    assert result.changed_objects == 1
    assert tuple(len(batch) for batch in embedder.batches) == (len(document["objects"]), 1)


def test_embedding_failure_does_not_activate_partial_revision(tmp_path):
    class WrongDimensions(DeterministicEmbedder):
        def embed(self, texts):
            return [(1.0,) for _ in texts]

    builder = BundleBuilder(tmp_path / "bundle")
    first = builder.build(native_document())
    with pytest.raises(ValueError, match="dimension"):
        BundleBuilder(builder.root, WrongDimensions()).build(native_document())
    assert json.loads((builder.root / "active.json").read_text())["revision"] == first.revision


def test_retry_after_embedding_failure_completes_same_revision(tmp_path):
    class TransientEmbedder(DeterministicEmbedder):
        fail = True

        def embed(self, texts):
            if self.fail:
                raise RuntimeError("temporary embedding failure")
            return super().embed(texts)

    embedder = TransientEmbedder()
    builder = BundleBuilder(tmp_path / "bundle", embedder)
    with pytest.raises(RuntimeError, match="temporary"):
        builder.build(native_document())
    assert not (builder.root / "active.json").exists()
    embedder.fail = False
    result = builder.build(native_document())
    with duckdb.connect(str(result.bundle / "catalog.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM embeddings").fetchone()[0] == len(native_document()["objects"])


def test_embedding_model_change_rebuilds_all_vectors(tmp_path):
    initial = DeterministicEmbedder()
    builder = BundleBuilder(tmp_path / "bundle", initial)
    first = builder.build(native_document())
    replacement = DeterministicEmbedder()
    replacement.model_id = "deterministic-v2"
    second = BundleBuilder(builder.root, replacement).build(native_document())
    assert first.revision != second.revision
    assert second.changed_objects == 0
    assert len(replacement.batches[0]) == len(native_document()["objects"])
