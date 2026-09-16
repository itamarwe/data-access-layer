import json
from dataclasses import replace

from dal.cli.main import main, build_parser
from dal.compiler import BundleBuilder
from tests.compiler.fixtures import native_document
from tests.application.test_join_availability import existence


def test_table_get_includes_bounded_columns_and_continuation(tmp_path, capsys):
    built = BundleBuilder(tmp_path / "bundle").build(native_document())
    prefix = ["--bundle", str(built.bundle)]
    assert main([*prefix, "table", "get", "table:orders", "--columns-limit", "1"]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["id"] == "table:orders"
    assert len(value["columns"]) == 1
    assert value["columns_page"] == {"limit": 1, "offset": 0, "has_more": True}
    assert "--offset 1" in value["next_commands"][0]
    assert main([*prefix, "table", "get", "table:orders", "--columns-limit", "1", "--columns-offset", "1"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["columns"][0]["id"] != value["columns"][0]["id"]
    assert not second["columns_page"]["has_more"]


def test_column_search_scopes_candidates_before_ranking_and_limit(tmp_path, capsys):
    document = native_document()
    document["objects"].extend({"id": f"column:customers.noise{i}", "kind": "column", "name": "customer_id", "parent_id": "table:customers"} for i in range(120))
    built = BundleBuilder(tmp_path / "bundle").build(document)
    prefix = ["--bundle", str(built.bundle), "column"]
    assert main([*prefix, "search", "customer_id", "--table", "table:orders"]) == 0
    value = json.loads(capsys.readouterr().out)
    assert [item["object"]["id"] for item in value["results"]] == ["column:orders.customer_id"]
    assert main([*prefix, "list", "--table", "table:orders"]) == 0
    assert len(json.loads(capsys.readouterr().out)["results"]) == 2


def test_table_evidence_supports_column_claim_and_limit_filters(tmp_path, capsys):
    evidence = [replace(existence(subject, True, offset=i), claim_path=claim) for i, (subject, claim) in enumerate([
        ("table:orders", "/exists"), ("column:orders.customer_id", "/exists"),
        ("column:orders.customer_id", "/description"), ("column:customers.id", "/exists"),
    ])]
    built = BundleBuilder(tmp_path / "bundle").build(native_document(), evidence)
    prefix = ["--bundle", str(built.bundle), "table", "evidence", "table:orders"]
    assert main([*prefix, "--column", "column:orders.customer_id", "--limit", "1"]) == 0
    assert len(json.loads(capsys.readouterr().out)["evidence"]) == 1
    assert main([*prefix, "--column", "column:orders.customer_id", "--claim", "/description", "--limit", "50"]) == 0
    values = json.loads(capsys.readouterr().out)["evidence"]
    assert [(item["subject_id"], item["claim_path"]) for item in values] == [("column:orders.customer_id", "/description")]
    assert main([*prefix, "--column", "column:customers.id"]) == 2
    assert "must belong" in json.loads(capsys.readouterr().err)["error"]


def test_default_search_budget_is_consistent_and_larger(tmp_path):
    from dal.application.models import DEFAULT_TOKEN_BUDGET, SearchOptions
    from tests.api.helpers import api_client
    assert DEFAULT_TOKEN_BUDGET == 3200
    assert SearchOptions().token_budget == DEFAULT_TOKEN_BUDGET
    assert build_parser().parse_args(["search", "orders"]).token_budget == DEFAULT_TOKEN_BUDGET
    schema = api_client(tmp_path).get("/api/v1/openapi.json").json()
    parameters = schema["paths"]["/api/v1/search"]["get"]["parameters"]
    assert next(value for value in parameters if value["name"] == "token_budget")["schema"]["default"] == DEFAULT_TOKEN_BUDGET
