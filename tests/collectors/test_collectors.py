import json
from datetime import datetime, timezone

from dal.collectors import collect_glue, collect_queries, collect_snapshot, refresh_document
from dal.identity import stable_id
from dal.model import validate_document

NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)


def test_query_usage_is_not_an_observed_join_and_cte_aliases_do_not_leak():
    result = collect_queries([
        {"sql": "SELECT * FROM sales.orders UNION ALL SELECT * FROM sales.customers"},
        {"sql": "SELECT * FROM sales.orders o JOIN sales.customers c ON o.customer_id = c.id"},
        {"sql": "WITH orders AS (SELECT * FROM sales.customers) SELECT * FROM orders o JOIN sales.products p ON o.id = p.id"},
        {"sql": "SELECT * FROM sales.orders o JOIN sales.customers c ON o.customer_id = c.id OR o.id = c.id"},
    ], collected_at=NOW)
    assert len(result.objects) == 1
    join = result.objects[0]
    assert join["left"] == [stable_id("column", "sales.orders.customer_id")]
    assert join["right"] == [stable_id("column", "sales.customers.id")]
    assert len([record for record in result.evidence if record.claim_path == "/usage/join_expression"]) == 1


def test_refresh_updates_schema_but_preserves_authored_values():
    original = {"version": 1, "objects": [
        {"id": "t", "kind": "table", "name": "Orders", "description": "Curated", "grain": {"description": "one order"}},
        {"id": "c", "kind": "column", "name": "id", "parent_id": "t", "data_type": "int"},
    ]}
    incoming = [
        {"id": "t", "kind": "table", "name": "Orders", "description": "Source comment"},
        {"id": "c", "kind": "column", "name": "id", "parent_id": "t", "data_type": "bigint"},
    ]
    result = refresh_document(original, incoming)
    assert result["objects"][0]["description"] == "Curated"
    assert result["objects"][0]["grain"] == {"description": "one order"}
    assert result["objects"][1]["data_type"] == "bigint"
    assert original["objects"][1]["data_type"] == "int"
    assert refresh_document(result, incoming) == result


def test_glue_paginates_and_keeps_partition_columns():
    class Paginator:
        def paginate(self, **kwargs):
            assert kwargs == {"DatabaseName": "sales"}
            yield {"TableList": [{"Name": "orders", "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]}, "PartitionKeys": [{"Name": "day", "Type": "date"}]}]}
    class Client:
        def get_paginator(self, name):
            assert name == "get_tables"
            return Paginator()
    result = collect_glue(Client(), ["sales"], collected_at=NOW)
    assert {item["name"] for item in result.objects if item["kind"] == "column"} == {"id", "day"}
    assert validate_document({"version": 1, "objects": list(result.objects)}) == ()
    assert all(record.layer.value == "physical" for record in result.evidence)


def test_snapshot_produces_reproducible_evidence(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"collected_at": NOW.isoformat(), "tables": [
        {"database": "sales", "table": {"Name": "orders", "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]}}},
    ], "queries": [{"sql": "select id from sales.orders"}]}))
    first, second = collect_snapshot(path), collect_snapshot(path)
    assert first == second
    assert validate_document({"version": 1, "objects": list(first.objects)}) == ()
