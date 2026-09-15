from collections import Counter

from dal.compiler import compilation_diagnostics, extract_records

from .fixtures import native_document


def test_extracts_native_resources_and_explicit_query_links():
    records = extract_records(native_document())
    assert Counter(obj.kind for obj in records.objects) == {
        "database": 1, "table": 2, "column": 3, "join": 1, "metric": 1,
        "doctrine": 1, "gold_query": 1, "entity": 1, "property": 1, "relation": 1,
    }
    assert {link.target_id for link in records.links if link.kind == "join_column"} == {
        "column:orders.customer_id", "column:customers.id",
    }
    assert {link.target_id for link in records.links if link.kind == "join_table"} == {"table:orders", "table:customers"}
    assert any(link.source_id == "entity:customer" and link.target_id == "column:orders.customer_id"
               for link in records.links if link.kind == "ontology_binding")
    assert any(link.source_id == "entity:customer" and link.target_id == "property:customer-id"
               for link in records.links if link.kind == "relation")
    assert "Exclude test orders" in next(obj.search_text for obj in records.objects if obj.kind == "doctrine")


def test_parent_search_payload_does_not_duplicate_children():
    objects = {obj.object_id: obj for obj in extract_records(native_document()).objects}
    assert "How many orders" not in objects["database:sales"].search_text
    assert "customer_id" not in objects["table:orders"].search_text


def test_invalid_reference_has_specific_diagnostic():
    document = native_document()
    document["objects"][6]["right"] = ["missing"]
    errors = compilation_diagnostics(document)
    assert any(error.pointer == "/objects/6/right" and "missing" in error.message for error in errors)


def test_duplicate_stable_id_is_rejected_before_storage():
    document = native_document()
    document["objects"][1]["id"] = document["objects"][0]["id"]
    assert any("duplicate stable ID" in issue.message for issue in compilation_diagnostics(document))
