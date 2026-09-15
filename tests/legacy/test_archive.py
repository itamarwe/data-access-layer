from __future__ import annotations

import hashlib
import json
import zipfile

import duckdb

from dal.compiler import compilation_diagnostics, extract_records
from dal.legacy import LegacyArchiveImporter
from dal.model import validate_document


def test_archive_imports_curated_ontology_doctrine_and_gold_queries(tmp_path):
    archive = tmp_path / "analyst.zip"
    _archive(archive, tmp_path / "context_graph.duckdb")
    before = hashlib.sha256(archive.read_bytes()).hexdigest()

    result = LegacyArchiveImporter(archive).convert("customer")

    assert validate_document(result.document) == ()
    assert compilation_diagnostics(result.document) == ()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == before
    records = extract_records(result.document)
    kinds = {item.kind for item in records.objects}
    assert {"entity", "relation", "doctrine", "gold_query"} <= kinds
    objects = result.document["objects"]
    assert next(item for item in objects if item["kind"] == "gold_query")["object_ids"]
    assert "Use joined identifiers carefully" in next(item for item in objects if item["kind"] == "doctrine")["content"]
    assert not any(item["kind"] == "property" and item["name"] == "PRODUCT" for item in objects)
    entity = next(item for item in objects if item["kind"] == "entity" and item["name"] == "PRODUCT")
    column = next(item for item in objects if item["kind"] == "column")
    assert column["id"] in entity["bindings"]


def _archive(path, database):
    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            "CREATE TABLE node_tables(table_name VARCHAR, status VARCHAR, grain VARCHAR, "
            "description VARCHAR, aliases VARCHAR)"
        )
        connection.execute(
            "INSERT INTO node_tables VALUES "
            "('shop.products', 'active', 'one row per product', 'Products', '')"
        )
        connection.execute(
            'CREATE TABLE node_columns(table_name VARCHAR, "column" VARCHAR, '
            "data_type VARCHAR, family VARCHAR, description VARCHAR)"
        )
        connection.execute(
            "INSERT INTO node_columns VALUES "
            "('shop.products', 'product_id', 'varchar', 'PRODUCT', 'Product identifier')"
        )
        connection.execute(
            "CREATE TABLE edges_join(table_a VARCHAR, col_a VARCHAR, table_b VARCHAR, "
            "col_b VARCHAR, join_count INTEGER)"
        )
        connection.execute(
            "CREATE TABLE edges_column(col_a VARCHAR, col_b VARCHAR, jaccard DOUBLE, "
            "observed_count BIGINT)"
        )
    finally:
        connection.close()
    assets = {
        "entity_definitions.json": {
            "_domain": {"title": "Shop catalog", "summary": "Find products."},
            "PRODUCT": {"definition": "An item offered for sale."},
        },
        "relation_names.json": {
            "products: PRODUCT.product_id ~ PRODUCT.related_product":
                "product is related to product",
        },
        "curated_questions.json": {
            "q1": {"question": "Which products are in the catalog?", "sql":
                   "SELECT product_id FROM shop.products"},
        },
    }
    with zipfile.ZipFile(path, "w") as target:
        target.write(database, "customer/assets/context_graph.duckdb")
        for name, value in assets.items():
            target.writestr(f"customer/assets/semantic/{name}", json.dumps(value))
        target.writestr(
            "customer/references/query-cookbook.md", "Use joined identifiers carefully.",
        )
