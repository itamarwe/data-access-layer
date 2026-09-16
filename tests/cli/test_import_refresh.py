import json

import pytest

from dal.cli.main import main
from dal.documents import dump_document, load_document
from tests.application.fixtures import native_document


@pytest.mark.parametrize("format", ["json", "yaml"])
def test_native_import_is_idempotent_and_preserves_authored_changes(tmp_path, capsys, format):
    source = tmp_path / f"source.{format}"
    source.write_text(dump_document(native_document(), format))
    root = tmp_path / "repo"
    args = ["--repository", str(root), "import", str(source)]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["imported_objects"] == 7
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["imported_objects"] == 0
    authored = root / "semantic" / "imported.yaml"
    value = load_document(authored.read_text())
    value["objects"][0]["description"] = "Reviewed by the curator"
    authored.write_text(dump_document(value))
    before = authored.read_bytes()
    assert main(args) == 2
    assert "conflicts" in capsys.readouterr().err
    assert authored.read_bytes() == before


def test_refresh_build_keeps_curation_and_updates_source_evidence(tmp_path, capsys):
    root = tmp_path / "repo"
    source = tmp_path / "snapshot.json"
    snapshot = {"collected_at": "2026-09-14T00:00:00Z", "tables": [{
        "database": "sales", "table": {"Name": "orders", "StorageDescriptor": {
            "Columns": [{"Name": "id", "Type": "integer"}],
        }},
    }]}
    source.write_text(json.dumps(snapshot))
    args = ["--repository", str(root), "build", "--refresh", str(source)]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["revision"] == first["revision"]
    authored = root / "semantic" / "collected.yaml"
    value = load_document(authored.read_text())
    table = next(item for item in value["objects"] if item["kind"] == "table")
    table["description"] = "Curated source meaning"
    authored.unlink()
    authored = root / "semantic" / "curated.json"
    authored.write_text(dump_document(value, "json"))
    snapshot["collected_at"] = "2026-09-15T00:00:00Z"
    snapshot["tables"][0]["table"]["Description"] = "Different schema comment"
    snapshot["tables"][0]["table"]["StorageDescriptor"]["Columns"].append({"Name": "amount", "Type": "double"})
    source.write_text(json.dumps(snapshot))
    assert main(args) == 0
    capsys.readouterr()
    objects = json.loads(authored.read_text())["objects"]
    assert next(item for item in objects if item["kind"] == "table")["description"] == "Curated source meaning"
    collected = load_document((root / "semantic" / "collected.yaml").read_text())["objects"]
    assert any(item["name"] == "amount" for item in collected)
    assert main(["--repository", str(root), "column", "search", "amount"]) == 0
    assert json.loads(capsys.readouterr().out)["results"]
