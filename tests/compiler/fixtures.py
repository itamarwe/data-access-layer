"""Native resources cover every kind and each compiled relationship."""


def native_document():
    return {"version": 1, "objects": [
        {"id": "database:sales", "kind": "database", "name": "sales", "description": "Curated sales model"},
        {"id": "table:orders", "kind": "table", "name": "orders", "source": "warehouse.orders", "parent_id": "database:sales"},
        {"id": "table:customers", "kind": "table", "name": "customers", "source": "warehouse.customers", "parent_id": "database:sales"},
        {"id": "column:orders.order_id", "kind": "column", "name": "order_id", "parent_id": "table:orders"},
        {"id": "column:orders.customer_id", "kind": "column", "name": "customer_id", "parent_id": "table:orders"},
        {"id": "column:customers.id", "kind": "column", "name": "id", "parent_id": "table:customers"},
        {"id": "join:order_customer", "kind": "join", "name": "Order customer", "left": ["column:orders.customer_id"], "right": ["column:customers.id"], "predicate": "orders.customer_id = customers.id"},
        {"id": "metric:orders", "kind": "metric", "name": "Order count", "expression": "COUNT(orders.order_id)", "object_ids": ["table:orders"]},
        {"id": "doctrine:revenue", "kind": "doctrine", "name": "Revenue policy", "content": "Exclude test orders.", "object_ids": ["table:orders"]},
        {"id": "gold_query:orders", "kind": "gold_query", "name": "Order count example", "question": "How many orders?", "sql": "SELECT COUNT(*) FROM orders", "dialect": "sqlite", "object_ids": ["table:orders"]},
        {"id": "entity:customer", "kind": "entity", "name": "Customer", "bindings": ["column:orders.customer_id"]},
        {"id": "property:customer-id", "kind": "property", "name": "CustomerId"},
        {"id": "relation:customer-id", "kind": "relation", "name": "identified_by", "from_id": "entity:customer", "to_id": "property:customer-id"},
    ]}
