"""Read-only extraction from the legacy Legacy DuckDB shape."""

import hashlib
from datetime import datetime, timezone

import duckdb

from dal.evidence import LegacyEvidenceExtractor, EvidenceLayer, SourceKind
from dal.identity import stable_id


def test_extracts_node_and_edge_evidence_without_mutating_database(tmp_path):
    database = tmp_path / "legacy.duckdb"
    _create_database(database)
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    records = tuple(LegacyEvidenceExtractor(
        database,
        source_revision="customer-graph-29",
        collected_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        batch_size=1,
    ).records())

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert {record.layer for record in records} == {
        EvidenceLayer.PHYSICAL, EvidenceLayer.USAGE, EvidenceLayer.CURATION,
    }
    assert all(record.source.revision == "customer-graph-29" for record in records)
    table_id = stable_id("table", "sales.orders")
    field_id = stable_id("column", "sales.orders.customer_id")
    assert _record(records, table_id, "/row_count").measurement.value == 42
    assert _record(records, table_id, "/description").claim_value == "Orders"
    assert _record(records, field_id, "/datatype").source.kind is SourceKind.DATABASE_SCHEMA
    relationship = stable_id(
        "join", "sales.customers.customer_id|sales.orders.customer_id",
    )
    assert _record(records, relationship, "/overlap/jaccard").measurement.value == 0.8
    assert _record(records, relationship, "/usage/join_count").source.kind is SourceKind.QUERY_LOG
    assert len({record.record_id for record in records}) == len(records)


def test_rejected_legacy_state_and_ranking_fields_are_not_imported(tmp_path):
    database = tmp_path / "legacy.duckdb"
    _create_database(database)

    records = tuple(LegacyEvidenceExtractor(
        database,
        source_revision="revision",
        collected_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    ).records())
    references = " ".join(record.content.uri for record in records)
    claim_paths = {record.claim_path for record in records}

    assert "status" not in references
    assert "retained" not in references
    assert "join_score" not in references
    assert "/status" not in claim_paths
    assert "/join_score" not in claim_paths


def _record(records, subject_id, claim_path):
    return next(
        record for record in records
        if record.subject_id == subject_id and record.claim_path == claim_path
    )


def _create_database(path):
    connection = duckdb.connect(str(path))
    connection.execute("""
        CREATE TABLE node_tables (
            table_name VARCHAR, schema VARCHAR, rows BIGINT, q90 INTEGER,
            users INTEGER, grain VARCHAR, description VARCHAR, status VARCHAR
        );
        INSERT INTO node_tables VALUES
            ('sales.orders', 'sales', 42, 9, 3, 'one row per order', 'Orders', 'dead');
        CREATE TABLE node_columns (
            table_name VARCHAR, "column" VARCHAR, data_type VARCHAR,
            cardinality_est BIGINT, description_schema VARCHAR,
            description_curated VARCHAR, derived_from VARCHAR
        );
        INSERT INTO node_columns VALUES
            ('sales.orders', 'customer_id', 'varchar', 12, 'Customer key', '', ''),
            ('sales.customers', 'customer_id', 'varchar', 12, 'Customer key', 'ID', '');
        CREATE TABLE edges_column (
            col_a VARCHAR, col_b VARCHAR, jaccard DOUBLE, inter_est BIGINT,
            observed_count BIGINT, retained BOOLEAN, join_score DOUBLE
        );
        INSERT INTO edges_column VALUES
            ('sales.orders.customer_id', 'sales.customers.customer_id', 0.8, 10, 7, true, 0.9),
            ('sales.orders.customer_id', 'sales.customers.customer_id', 0.8, 10, 7, false, 0.1);
        CREATE TABLE edges_join (
            table_a VARCHAR, col_a VARCHAR, table_b VARCHAR, col_b VARCHAR,
            join_count INTEGER
        );
        INSERT INTO edges_join VALUES
            ('sales.orders', 'customer_id', 'sales.customers', 'customer_id', 7);
    """)
    connection.close()
