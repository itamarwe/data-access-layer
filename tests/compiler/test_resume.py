"""Interrupted builds resume without exposing partial revisions."""

import dal.compiler.build as build_module
import duckdb
import pytest
from dal.compiler import BundleBuilder

from .fixtures import native_document


def test_database_complete_interruption_resumes(monkeypatch, tmp_path):
    root = tmp_path / "bundle"
    builder = BundleBuilder(root)
    original = build_module.write_json_atomic
    interrupted = False

    def fail_manifest(path, value):
        nonlocal interrupted
        if path.name == "manifest.json" and not interrupted:
            interrupted = True
            raise RuntimeError("interrupted after database commit")
        original(path, value)

    monkeypatch.setattr(build_module, "write_json_atomic", fail_manifest)
    try:
        builder.build(native_document())
    except RuntimeError:
        pass
    else:
        raise AssertionError("the simulated interruption did not run")
    assert not (root / "active.json").exists()
    assert len(tuple((root / ".builds").iterdir())) == 1

    monkeypatch.setattr(build_module, "write_json_atomic", original)
    result = builder.build(native_document())

    assert result.bundle.is_dir()
    assert (root / "active.json").is_file()
    assert tuple((root / ".builds").iterdir()) == ()


@pytest.mark.parametrize("damage", ["missing_database", "wrong_evidence"])
def test_interrupted_incremental_build_restores_verified_inputs(monkeypatch, tmp_path, damage):
    builder = BundleBuilder(tmp_path / "bundle")
    builder.build(native_document())
    document = native_document()
    document["objects"][0]["description"] = "Changed database description"
    original = build_module.write_json_atomic

    def interrupt(path, value):
        if path.name == "manifest.json":
            raise RuntimeError("interrupted after transaction")
        return original(path, value)

    monkeypatch.setattr(build_module, "write_json_atomic", interrupt)
    with pytest.raises(RuntimeError):
        builder.build(document)
    work = next((builder.root / ".builds").iterdir())
    if damage == "missing_database":
        (work / "catalog.duckdb").unlink()
    else:
        (work / "evidence.json").write_text("not the requested snapshot")
    monkeypatch.setattr(build_module, "write_json_atomic", original)
    result = builder.build(document)
    with duckdb.connect(str(result.bundle / "catalog.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM objects").fetchone()[0] == len(document["objects"])
        assert db.execute("SELECT count(*) FROM links").fetchone()[0] > 0
    from dal.evidence import serialize_snapshot
    assert (result.bundle / "evidence.json").read_bytes() == serialize_snapshot(())
