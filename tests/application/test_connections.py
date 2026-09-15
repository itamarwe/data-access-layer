from dataclasses import asdict
from datetime import datetime, timezone
import json

import pytest

from dal.application import BundleCatalog, CatalogService, SearchOptions
from dal.compiler import BundleBuilder
from dal.collectors import collect_queries
from dal.model import validate_document
from tests.compiler.fixtures import native_document


def service(tmp_path, document=None):
    bundle = BundleBuilder(tmp_path / "bundle").build(document or native_document())
    return CatalogService(BundleCatalog(bundle.bundle))


def test_domain_connections_are_three_distinct_groups(tmp_path):
    catalog = service(tmp_path)
    result = catalog.connections("entity:customer")
    assert set(asdict(result)) == {"relations", "joins", "mappings"}
    assert result.relations[0].name == "identified_by"
    assert result.relations[0].id == "relation:customer-id"
    assert result.mappings[0].source_id == "entity:customer"
    assert result.mappings[0].target_id == "column:orders.customer_id"
    assert not result.joins


def test_join_has_table_endpoints_and_keeps_its_complete_definition(tmp_path):
    result = service(tmp_path).connections("table:orders")
    assert len(result.joins) == 1
    join = result.joins[0]
    assert (join.source_id, join.target_id) == ("table:orders", "table:customers")
    assert join.details["predicate"] == "orders.customer_id = customers.id"
    assert join.details["left"] == ["column:orders.customer_id"]
    assert not result.relations and not result.mappings


def test_composite_join_is_one_connection_not_many_index_edges(tmp_path):
    document = native_document()
    document["objects"].append({"id": "column:customers.order_id", "kind": "column",
                                "name": "order_id", "parent_id": "table:customers"})
    join = document["objects"][6]
    join["left"].append("column:orders.order_id")
    join["right"].append("column:customers.order_id")
    join["predicate"] += " AND orders.order_id = customers.order_id"
    result = service(tmp_path, document).connections("join:order_customer")
    assert len(result.joins) == 1
    assert len(result.joins[0].details["left"]) == 2


def test_membership_and_knowledge_references_are_navigation_not_domain_connections(tmp_path):
    catalog = service(tmp_path)
    assert asdict(catalog.connections("doctrine:revenue")) == {"relations": (), "joins": (), "mappings": ()}
    navigation = catalog.neighbors("doctrine:revenue")
    assert [(item.via, item.object.id) for item in navigation] == [("object_ids", "table:orders")]
    assert any(item.via == "children" for item in catalog.neighbors("database:sales"))
    assert any(item.object.id == "relation:customer-id" for item in catalog.neighbors("entity:customer"))
    assert {item.object.id for item in catalog.neighbors("relation:customer-id")} == {"entity:customer", "property:customer-id"}
    assert all("relationship" not in asdict(item) for item in navigation)


def test_search_never_exposes_internal_adjacency_labels_and_respects_budget(tmp_path):
    response = service(tmp_path).search("orders customer", options=SearchOptions(token_budget=1600))
    payload = asdict(response)
    assert set(payload["connections"]) == {"relations", "joins", "mappings"}
    assert "relationships" not in payload
    assert not any(label in json.dumps(payload["connections"]) for label in ("join_column", "join_table", "ontology_binding"))
    assert response.estimated_tokens <= 1600


def test_reverse_or_wrong_kind_mapping_is_rejected():
    document = native_document()
    document["objects"][4]["bindings"] = ["entity:customer"]
    assert any("mappings must go" in item.message for item in validate_document(document))


def test_conditions_and_join_behavior_do_not_overwrite_each_other():
    sql = "SELECT * FROM sales.orders o JOIN sales.customers c ON o.customer_id = c.id"
    queries = [{"sql": sql}, {"sql": sql + " AND c.is_current = true"},
               {"sql": sql.replace(" JOIN ", " LEFT JOIN ")}]
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    first = collect_queries(queries, collected_at=now)
    reverse = collect_queries(list(reversed(queries)), collected_at=now)
    assert len(first.objects) == 3
    assert sorted(first.objects, key=lambda item: item["id"]) == sorted(reverse.objects, key=lambda item: item["id"])
    assert len(collect_queries([queries[0], queries[0]], collected_at=now).objects) == 1


def test_unknown_resource_has_empty_connection_groups(tmp_path):
    assert asdict(service(tmp_path).connections("missing")) == {"relations": (), "joins": (), "mappings": ()}


def test_outer_join_direction_does_not_depend_on_on_operand_order():
    from dal.identity import stable_id
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    joins = collect_queries([
        {"sql": "SELECT * FROM sales.orders o LEFT JOIN sales.customers c ON o.customer_id = c.id"},
        {"sql": "SELECT * FROM sales.customers c LEFT JOIN sales.orders o ON o.customer_id = c.id"},
    ], collected_at=now).objects
    assert len(joins) == 2
    assert joins[0]["right"] == [stable_id("column", "sales.customers.id")]
    assert joins[1]["right"] == [stable_id("column", "sales.orders.customer_id")]
