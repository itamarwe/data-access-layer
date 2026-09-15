import json

from dal.legacy import LegacyGraphImporter
from dal.model import validate_document


def test_import_old_graph_consolidates_nodes_and_does_not_turn_co_usage_into_join(tmp_path):
    path = tmp_path / "graph.json"
    value = {"nodes": [
        {"id": "sales", "kind": "database", "name": "sales"},
        {"id": "sales.orders", "kind": "table", "database": "sales", "name": "orders", "row_count_estimate": 0},
        {"id": "sales.customers", "kind": "table", "database": "sales", "name": "customers"},
        {"id": "sales.orders.customer_id", "kind": "column", "table_id": "sales.orders", "name": "customer_id", "type": "bigint"},
        {"id": "sales.customers.id", "kind": "column", "table_id": "sales.customers", "name": "id", "type": "bigint"},
    ], "join_specs": [{
        "id": "j1", "left": "sales.orders.customer_id", "right": "sales.customers.id",
        "condition": "lower(orders.customer_id) = lower(customers.id)",
        "evidence": {"usage_evidence": {"co_occurrence": 20, "explicit_joins": 0}},
    }], "edges": [{"id": "co1", "kind": "CO_QUERIED_WITH", "src": "sales.orders", "dst": "sales.customers"}]}
    path.write_text(json.dumps(value))
    result = LegacyGraphImporter(path).convert()
    assert validate_document(result.document) == ()
    join = next(item for item in result.document["objects"] if item["kind"] == "join")
    assert "predicate" not in join
    assert any(record.claim_path == "/row_count_estimate" and record.claim_value == 0 for record in result.evidence)
    assert any(record.claim_path == "/usage/relationship" for record in result.evidence)
