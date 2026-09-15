"""Small native catalog shared by delivery adapter tests."""


def native_document():
    return {"version": 1, "objects": [
        {"id": "urn:dal:table:orders", "kind": "table", "name": "orders", "source": "warehouse.orders",
         "description": "Orders placed by customers"},
        {"id": "urn:dal:table:customers", "kind": "table", "name": "customers", "source": "warehouse.customers"},
        {"id": "urn:dal:column:orders.customer_id", "kind": "column", "name": "customer_id",
         "parent_id": "urn:dal:table:orders", "data_type": "integer"},
        {"id": "urn:dal:column:customers.id", "kind": "column", "name": "id",
         "parent_id": "urn:dal:table:customers", "data_type": "integer"},
        {"id": "urn:dal:join:orders-customers", "kind": "join", "name": "Orders customer join",
         "left": ["urn:dal:column:orders.customer_id"], "right": ["urn:dal:column:customers.id"],
         "predicate": "orders.customer_id = customers.id", "cardinality": "many-to-one",
         "required_filters": ["customers.is_current = true"]},
        {"id": "urn:dal:gold_query:orders", "kind": "gold_query", "name": "How many orders?",
         "question": "How many orders?", "sql": "SELECT COUNT(*) FROM warehouse.orders", "dialect": "duckdb",
         "object_ids": ["urn:dal:table:orders"]},
        {"id": "urn:dal:doctrine:orders", "kind": "doctrine", "name": "Orders methodology",
         "content": "Count orders after excluding test orders.", "object_ids": ["urn:dal:table:orders"]},
    ]}
