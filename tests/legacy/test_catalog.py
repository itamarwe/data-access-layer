"""Legacy graph migration tests using the real table shapes."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import duckdb

from dal.compiler import compilation_diagnostics
from dal.evidence import LegacyEvidenceExtractor
from dal.legacy import LegacyCatalogImporter
from dal.model import validate_document


def test_catalog_and_evidence_convert_to_valid_native_model(tmp_path):
    database = tmp_path / "context_graph.duckdb"
    _legacy_database(database)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    extractor = LegacyEvidenceExtractor(
        database, "fixture-v1", datetime(2026, 9, 7, tzinfo=timezone.utc),
    )

    result = LegacyCatalogImporter(database).convert(
        "legacy", extractor.records(),
    )

    assert (result.tables, result.fields, result.relationships) == (2, 3, 1)
    assert result.diagnostics == ()
    assert validate_document(result.document) == ()
    assert compilation_diagnostics(result.document) == ()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_legacy_statuses_are_consolidated_and_missing_grain_is_absent(tmp_path):
    database = tmp_path / "context_graph.duckdb"
    _legacy_database(database)

    document = LegacyCatalogImporter(database).convert("legacy").document
    orders, customers = [item for item in document["objects"] if item["kind"] == "table"]

    assert orders["status"] == "published"
    assert customers["status"] == "deprecated"
    assert "grain" not in customers


def test_physical_only_relationship_does_not_fabricate_join_predicate(tmp_path):
    database = tmp_path / "context_graph.duckdb"
    _legacy_database(database)
    connection = duckdb.connect(str(database))
    connection.execute("DELETE FROM edges_join")
    connection.close()
    result = LegacyCatalogImporter(database).convert("legacy")
    join = next(item for item in result.document["objects"] if item["kind"] == "join")
    assert "predicate" not in join
    assert join["left"] and join["right"]


def _legacy_database(path):
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE node_tables(table_name VARCHAR, status VARCHAR, grain VARCHAR, "
            "description VARCHAR, aliases VARCHAR)"
        )
        connection.executemany("INSERT INTO node_tables VALUES (?, ?, ?, ?, ?)", [
            ("sales.orders", "active", "one row per order", "Orders", "purchases | bookings"),
            ("sales.customers", "dead", "", "Customers", ""),
        ])
        connection.execute(
            "CREATE TABLE node_columns(table_name VARCHAR, \"column\" VARCHAR, data_type VARCHAR, "
            "family VARCHAR, description VARCHAR)"
        )
        connection.executemany("INSERT INTO node_columns VALUES (?, ?, ?, ?, ?)", [
            ("sales.orders", "order_id", "bigint", "ORDER_ID", "Order identifier"),
            ("sales.orders", "customer_id", "varchar", "CUSTOMER_ID", "Customer identifier"),
            ("sales.customers", "id", "varchar", "CUSTOMER_ID", "Customer identifier"),
        ])
        connection.execute(
            "CREATE TABLE edges_column(col_a VARCHAR, col_b VARCHAR, jaccard DOUBLE, "
            "observed_count BIGINT)"
        )
        connection.execute(
            "INSERT INTO edges_column VALUES "
            "('sales.orders.customer_id', 'sales.customers.id', 0.9, 3)"
        )
        connection.execute(
            "CREATE TABLE edges_join(table_a VARCHAR, col_a VARCHAR, table_b VARCHAR, "
            "col_b VARCHAR, join_count INTEGER)"
        )
        connection.execute(
            "INSERT INTO edges_join VALUES "
            "('sales.orders', 'customer_id', 'sales.customers', 'id', 3)"
        )
    finally:
        connection.close()
