from dal.health import PhysicalTable, inspect_health
from .helpers import authored_repository, request, table, CatalogSnapshot


def test_missing_changed_and_stale_sources_have_recovery(tmp_path):
    authored_repository(tmp_path)
    snapshot = CatalogSnapshot([table("warehouse.orders", {"customer_id": "string", "new": "integer"}, age_days=4)])
    result = inspect_health(request(tmp_path, physical_catalog=snapshot))
    assert {"SOURCE_SCHEMA_DRIFT", "SOURCE_DATA_STALE", "SOURCE_TABLE_MISSING"} <= {x.code for x in result.failures}
    assert "SOURCE_COLUMN_NOT_MODELED" in {x.code for x in result.gaps}
    assert all(x.recovery_command for x in result.failures)


def test_unknown_data_time_is_not_claimed_fresh(tmp_path):
    authored_repository(tmp_path)
    snapshot = CatalogSnapshot([
        PhysicalTable("warehouse.orders", {"customer_id": "integer"}, None),
        table("warehouse.customers", {"id": "integer"}),
    ])
    result = inspect_health(request(tmp_path, physical_catalog=snapshot))
    assert result.healthy
    assert "DATA_FRESHNESS_NOT_CHECKED" in {x.code for x in result.gaps}


def test_live_io_is_not_required_for_health(tmp_path):
    authored_repository(tmp_path)
    snapshot = CatalogSnapshot([table("warehouse.orders", {"customer_id": "integer"}), table("warehouse.customers", {"id": "integer"})])
    result = inspect_health(request(tmp_path, physical_catalog=snapshot))
    assert result.healthy
    assert any(check["name"] == "physical" and check["performed"] for check in result.checks)
