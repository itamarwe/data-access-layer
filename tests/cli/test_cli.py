import json

from dal.cli.main import main
from dal.compiler import BundleBuilder
from tests.application.fixtures import native_document


def _bundle(tmp_path):
    return BundleBuilder(tmp_path / "bundle").build(native_document()).bundle


def test_global_search_is_json_and_empty_results_are_an_array(tmp_path, capsys):
    code = main(["--bundle", str(_bundle(tmp_path)), "search", "not-in-catalog"])

    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["results"] == []
    assert output["start_with"] is None


def test_typed_list_and_get(tmp_path, capsys):
    bundle = _bundle(tmp_path)
    before = {
        path.relative_to(bundle): path.read_bytes()
        for path in bundle.rglob("*") if path.is_file()
    }

    assert main(["--bundle", str(bundle), "table", "list"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert [item["name"] for item in listing["results"]] == ["customers", "orders"]

    assert main(["--bundle", str(bundle), "gold-query", "get",
                 "urn:dal:gold_query:orders"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["kind"] == "gold_query"
    after = {
        path.relative_to(bundle): path.read_bytes()
        for path in bundle.rglob("*") if path.is_file()
    }
    assert after == before


def test_invalid_weight_fails_without_fake_success(tmp_path, capsys):
    code = main(["--bundle", str(_bundle(tmp_path)), "search", "orders",
                 "--weight", "magic=1"])

    error = json.loads(capsys.readouterr().err)
    assert code == 2
    assert "unknown ranking weights" in error["error"]


def test_typed_context_actions_expose_bounded_neighbors_and_evidence(tmp_path, capsys):
    bundle = _bundle(tmp_path)
    prefix = ["--bundle", str(bundle), "table"]
    assert main([*prefix, "neighbors", "urn:dal:table:orders", "--limit", "1"]) == 0
    assert len(json.loads(capsys.readouterr().out)["neighbors"]) == 1
    assert main([*prefix, "evidence", "urn:dal:table:orders"]) == 0
    assert json.loads(capsys.readouterr().out)["evidence"] == []


def test_connections_command_returns_separate_domain_groups(tmp_path, capsys):
    assert main(["--bundle", str(_bundle(tmp_path)), "connections", "urn:dal:table:orders"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result) == {"relations", "joins", "mappings"}
    assert len(result["joins"]) == 1
