"""Unsupported imports fail without touching sources or repositories."""

import json

import pytest

from dal.cli.main import main
from dal.documents import dump_document, load_document
from dal.evidence import SnapshotRepository
from dal.identity import stable_id
from tests.application.fixtures import native_document


@pytest.mark.parametrize("suffix", [".duckdb", ".DUCKDB", ".zip", ".ZIP"])
@pytest.mark.parametrize("existing_repository", [False, True])
def test_unsupported_import_does_not_write(tmp_path, capsys, suffix, existing_repository):
    source = tmp_path / f"catalog{suffix}"
    original = b"\x00\xffnot a native document"
    source.write_bytes(original)
    root = tmp_path / "repo"
    if existing_repository:
        semantic = root / "semantic"
        semantic.mkdir(parents=True)
        (semantic / "catalog.yaml").write_text(dump_document(native_document()))
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    assert main(["--repository", str(root), "import", str(source)]) == 2

    output = capsys.readouterr()
    assert not output.out
    error = json.loads(output.err)
    assert error["type"] == "ValueError"
    assert "not supported" in error["error"]
    assert "native DAL JSON/YAML" in error["error"]
    assert source.read_bytes() == original
    assert root.exists() == existing_repository
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


def test_former_dal_json_graph_import_preserves_evidence(tmp_path, capsys):
    source = tmp_path / "graph.json"
    source.write_text(json.dumps({"nodes": [
        {"id": "sales", "kind": "database", "name": "sales"},
        {"id": "sales.orders", "kind": "table", "database": "sales",
         "name": "orders", "row_count_estimate": 0},
    ]}))
    root = tmp_path / "repo"

    assert main(["--repository", str(root), "import", str(source)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["imported_objects"] == 2
    document = load_document((root / "semantic" / "imported.yaml").read_text())
    assert {item["kind"] for item in document["objects"]} == {"database", "table"}
    records = SnapshotRepository(root / "evidence").get(result["evidence"]["snapshot_id"])
    assert any(record.subject_id == stable_id("table", "sales.orders")
               and record.claim_path == "/row_count_estimate" and record.claim_value == 0
               for record in records)
