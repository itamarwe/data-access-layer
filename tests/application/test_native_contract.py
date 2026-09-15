import json
import math
from dataclasses import asdict

import pytest

from dal.application import BundleCatalog, CatalogService
from dal.application.models import SearchOptions
from dal.compiler import BundleBuilder
from tests.application.fixtures import native_document


def service(root, document=None):
    BundleBuilder(root).build(document or native_document())
    return CatalogService(BundleCatalog(root))


def test_deprecated_objects_are_excluded_before_ranking_and_listing(tmp_path):
    document = native_document()
    document["objects"][0]["status"] = "deprecated"
    catalog = service(tmp_path, document)
    assert all(item.name != "orders" for item in catalog.list("table"))
    assert catalog.search_kind("table", "orders").results == ()
    assert catalog.search_kind("table", "orders", options=SearchOptions(include_deprecated=True)).results
    assert catalog.get("table", "urn:dal:table:orders") is not None


def test_a_long_lived_service_observes_the_next_activated_revision(tmp_path):
    catalog = service(tmp_path)
    assert catalog.get("table", "urn:dal:table:orders").name == "orders"
    document = native_document()
    document["objects"][0]["name"] = "purchases"
    BundleBuilder(tmp_path).build(document)
    assert catalog.get("table", "urn:dal:table:orders").name == "purchases"


def test_join_response_includes_complete_predicate_and_required_filters(tmp_path):
    response = service(tmp_path).search_kind("join", "orders customers")
    details = response.results[0].details
    assert details["predicate"] == "orders.customer_id = customers.id"
    assert details["required_filters"] == ["customers.is_current = true"]
    assert details["left"] == ["urn:dal:column:orders.customer_id"]


@pytest.mark.parametrize("budget", [400, 500, 800, 1600])
def test_low_budgets_remove_whole_action_units(tmp_path, budget):
    document = native_document()
    query = next(item for item in document["objects"] if item["kind"] == "gold_query")
    query["sql"] = "SELECT " + ",".join(f"'{i}' AS col{i}" for i in range(1000))
    response = service(tmp_path, document).search_kind("gold_query", "How many orders?", options=SearchOptions(token_budget=budget))
    serialized = json.dumps(asdict(response), default=str, ensure_ascii=False).encode("utf-8")
    assert response.estimated_tokens == math.ceil(len(serialized) / 4)
    assert response.estimated_tokens <= budget
    assert all(item.details["sql"] == query["sql"] for item in response.results)
    assert response.omissions.total_matches == 1
    assert any(item.id == query["id"] for item in response.also_matched)


def test_budget_below_minimum_and_oversized_query_are_explicit_errors(tmp_path):
    with pytest.raises(ValueError, match="minimum"):
        SearchOptions(token_budget=399)
    with pytest.raises(ValueError, match="shorten"):
        service(tmp_path).search("unmatched " * 1000, options=SearchOptions(token_budget=400))


def test_typed_search_includes_only_applicable_doctrine(tmp_path):
    catalog = service(tmp_path)
    response = catalog.search_kind("table", "orders")
    assert response.relevant_doctrine.id == "urn:dal:doctrine:orders"
    assert catalog.search_kind("table", "customers", options=SearchOptions(max_details=1)).relevant_doctrine is None


def test_active_revision_cannot_escape_bundle_directory(tmp_path):
    (tmp_path / "active.json").write_text('{"revision": "../../outside"}')
    with pytest.raises(ValueError, match="invalid active"):
        BundleCatalog(tmp_path)


def test_database_revision_must_match_manifest(tmp_path):
    import duckdb

    built = BundleBuilder(tmp_path).build(native_document())
    with duckdb.connect(str(built.bundle / "catalog.duckdb")) as connection:
        connection.execute("UPDATE meta SET value='different' WHERE key='revision'")
    with pytest.raises(ValueError, match="database revision"):
        BundleCatalog(tmp_path)
