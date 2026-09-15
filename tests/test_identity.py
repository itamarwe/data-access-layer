from dal.identity import stable_id


def test_stable_id_is_deterministic_and_kind_scoped():
    assert stable_id("dataset", "warehouse.orders") == stable_id(
        "dataset", "warehouse.orders",
    )
    assert stable_id("dataset", "warehouse.orders") != stable_id(
        "field", "warehouse.orders",
    )
    assert stable_id("dataset", "warehouse.orders").startswith("urn:dal:dataset:")
