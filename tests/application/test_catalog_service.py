from pathlib import Path

from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from tests.application.fixtures import native_document


def _service(tmp_path: Path) -> CatalogService:
    bundle = BundleBuilder(tmp_path / "bundle").build(native_document()).bundle
    return CatalogService(BundleCatalog(bundle))


def test_search_returns_bounded_progressive_context(tmp_path):
    response = _service(tmp_path).search("How many orders?")

    assert response.start_with is not None
    assert response.estimated_tokens <= 3200
    assert any(item.object.id == "urn:dal:gold_query:orders" for item in response.results)
    assert len(response.next_commands) <= 2
    assert response.omissions.total_matches >= len(response.results)
    assert response.estimated_tokens > 0
    assert response.capabilities.lexical == "bm25"
    assert response.capabilities.embedding == "unavailable"


def test_empty_search_has_no_synthetic_result_or_next_step(tmp_path):
    response = _service(tmp_path).search("term-that-does-not-exist")

    assert response.results == ()
    assert response.start_with is None
    assert response.next_commands == ()
    assert response.omissions.total_matches == 0


def test_typed_list_get_and_search_share_catalog(tmp_path):
    service = _service(tmp_path)

    datasets = service.list("table")
    orders = service.get("table", "urn:dal:table:orders")
    response = service.search_kind("table", "orders")

    assert {item.name for item in datasets} == {"customers", "orders"}
    assert orders is not None and orders.source == "warehouse.orders"
    assert all(item.object.kind == "table" for item in response.results)
    assert service.get("column", "urn:dal:table:orders") is None


def test_catalog_accepts_compiler_root_with_active_pointer(tmp_path):
    root = tmp_path / "bundle"
    BundleBuilder(root).build(native_document())

    assert CatalogService(BundleCatalog(root)).get(
        "table", "urn:dal:table:orders"
    ) is not None


def test_missing_dataset_grain_is_a_gap_not_a_build_failure(tmp_path):
    response = _service(tmp_path).search_kind("table", "orders")

    assert any(gap.code == "grain_missing" for gap in response.gaps)


def test_neighbors_are_bounded_and_resolve_objects(tmp_path):
    service = _service(tmp_path)

    neighbors = service.neighbors("urn:dal:table:orders", limit=2)

    assert len(neighbors) <= 2
    assert all(item.object is not None for item in neighbors)


def test_evidence_reader_is_bounded(tmp_path):
    service = _service(tmp_path)

    assert service.evidence("urn:dal:table:orders", limit=1) == ()
