from datetime import datetime, timedelta, timezone

import pytest

from dal.application import BundleCatalog, CatalogService, SearchOptions
from dal.compiler import BundleBuilder
from dal.evidence import ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource, SourceKind, SnapshotRepository
from dal.health import inspect_health
from tests.compiler.fixtures import native_document
from tests.health.helpers import authored_repository, request, CatalogSnapshot, table


def existence(subject, exists, *, offset=0, layer=EvidenceLayer.PHYSICAL):
    return EvidenceRecord(
        record_id=f"urn:dal:evidence:exists-{offset}-{exists}-{layer.value}", layer=layer,
        subject_id=subject, claim_path="/exists", claim_value=exists,
        source=EvidenceSource(SourceKind.DATABASE_SCHEMA if layer == EvidenceLayer.PHYSICAL else SourceKind.CURATION, f"snapshot:{offset}:{exists}"),
        collected_at=datetime(2026, 9, 7, tzinfo=timezone.utc) + timedelta(hours=offset),
        content=ContentReference("snapshot:existence", "a" * 64),
    )


def service(root, document, evidence=()):
    built = BundleBuilder(root / "bundle").build(document, evidence)
    return CatalogService(BundleCatalog(built.bundle))


@pytest.mark.parametrize("target", ["table:customers", "column:customers.id"])
@pytest.mark.parametrize("field,value", [("status", "deprecated"), ("restricted", True)])
def test_unusable_join_is_not_served_through_any_discovery_path(tmp_path, target, field, value):
    document = native_document()
    next(item for item in document["objects"] if item["id"] == target)[field] = value
    catalog = service(tmp_path, document)
    identifier = "join:order_customer"
    assert catalog.get("join", identifier) is None
    assert catalog.resolve([identifier]) == ()
    assert catalog.list("join", include_deprecated=True) == ()
    assert not catalog.connections("table:orders").joins
    assert not catalog.connections(identifier).joins
    assert all(item.object.id != identifier for item in catalog.neighbors("table:orders"))
    result = catalog.search("Order customer", options=SearchOptions(include_deprecated=True))
    assert identifier not in {item.object.id for item in result.results}
    assert identifier not in {item.id for item in result.also_matched}
    assert not result.connections.joins
    authored_repository(tmp_path, document)
    issues = inspect_health(request(tmp_path)).failures
    assert any(item.code == "JOIN_DEPENDENCY_UNAVAILABLE" and item.location == identifier for item in issues)


def test_latest_physical_absence_blocks_join_and_later_existence_restores_it(tmp_path):
    document = native_document()
    absent = existence("table:customers", False)
    present = existence("table:customers", True, offset=1)
    assert service(tmp_path, document, [absent]).get("join", "join:order_customer") is None
    assert service(tmp_path, document, [present, absent]).get("join", "join:order_customer") is not None
    # Curation is not a physical existence check; equal-time disagreement is unsafe.
    assert service(tmp_path, document, [absent, existence("table:customers", True)]).get("join", "join:order_customer") is None
    assert service(tmp_path, document, [existence("table:customers", False, layer=EvidenceLayer.CURATION)]).get("join", "join:order_customer") is not None
    authored_repository(tmp_path, document)
    SnapshotRepository(tmp_path / "evidence").put([absent])
    result = inspect_health(request(tmp_path, evidence_directory=tmp_path / "evidence"))
    assert any(item.code == "JOIN_DEPENDENCY_UNAVAILABLE" for item in result.failures)


def test_health_reports_join_affected_by_explicit_missing_physical_table(tmp_path):
    authored_repository(tmp_path, native_document())
    result = inspect_health(request(tmp_path, physical_catalog=CatalogSnapshot([
        table("warehouse.orders", {"order_id": "integer", "customer_id": "integer"}),
    ])))
    assert any(item.code == "SOURCE_TABLE_MISSING" for item in result.failures)
    assert any(item.code == "JOIN_DEPENDENCY_UNAVAILABLE" for item in result.failures)


def test_missing_endpoint_is_a_health_failure_and_cannot_build(tmp_path):
    from dal.compiler.build import CompilationError
    document = native_document()
    document["objects"] = [item for item in document["objects"] if item["id"] != "column:customers.id"]
    authored_repository(tmp_path, document)
    assert not inspect_health(request(tmp_path)).healthy
    with pytest.raises(CompilationError):
        service(tmp_path, document)


def test_blocked_join_does_not_consume_connection_page(tmp_path):
    document = native_document()
    document["objects"].extend([
        {"id": "table:retired", "kind": "table", "name": "Retired", "status": "deprecated"},
        {"id": "column:retired.id", "kind": "column", "name": "id", "parent_id": "table:retired"},
        {"id": "join:aaa", "kind": "join", "name": "A bad join", "left": ["column:orders.customer_id"], "right": ["column:retired.id"]},
    ])
    catalog = service(tmp_path, document)
    assert catalog.list("join", limit=1)[0].id == "join:order_customer"
    assert catalog.connections("table:orders", limit=1).joins[0].id == "join:order_customer"
