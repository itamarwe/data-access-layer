"""Validate the guide's native example, not an agent's classification behavior."""

import json
from pathlib import Path

from dal.cli.main import main
from dal.documents import load_document


def test_authoring_example_keeps_object_facts_and_methodology_in_native_fields(tmp_path, capsys):
    guide = (Path(__file__).parents[2] / "skills/dal/references/authoring.md").read_text()
    catalog = guide.split("```yaml\n", 1)[1].split("```", 1)[0]
    document = load_document(catalog)
    indexed = {item["id"]: item for item in document["objects"]}
    assert indexed["column:orders.amount"]["unit"] == "cents"
    assert indexed["table:orders"]["grain"]["description"] == "One row per order."
    doctrines = [item for item in document["objects"] if item["kind"] == "doctrine"]
    assert len(doctrines) == 2
    assert indexed["doctrine:actuals-versus-targets"]["object_ids"] == ["table:orders", "table:targets"]
    assert indexed["doctrine:incomplete-period-comparison"]["object_ids"] == []

    semantic = tmp_path / "semantic"
    semantic.mkdir()
    (semantic / "catalog.yaml").write_text(catalog)

    def invoke(*args):
        assert main(["--repository", str(tmp_path), *args]) == 0
        return json.loads(capsys.readouterr().out)

    invoke("validate")
    invoke("build")
    column = invoke("column", "get", "column:orders.amount")
    assert column["payload"]["unit"] == "cents"
    table = invoke("table", "get", "table:orders")
    assert table["payload"]["grain"] == indexed["table:orders"]["grain"]
    for identifier in ("doctrine:actuals-versus-targets", "doctrine:incomplete-period-comparison"):
        found = invoke("doctrine", "get", identifier)
        assert found["payload"]["object_ids"] == indexed[identifier]["object_ids"]
    result = invoke("doctrine", "search", "incomplete reporting periods")
    assert any(item["object"]["id"] == "doctrine:incomplete-period-comparison" for item in result["results"])
