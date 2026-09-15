from urllib.parse import quote

from .helpers import api_client


def test_connections_endpoint_separates_joins_from_resource_navigation(tmp_path):
    client = api_client(tmp_path)
    response = client.get("/api/v1/graph/connections", params={"object_id": "urn:dal:table:orders"})
    assert response.status_code == 200
    assert set(response.json()) == {"relations", "joins", "mappings"}
    assert len(response.json()["joins"]) == 1
    navigation = client.get("/api/v1/graph/neighbors", params={"object_id": "urn:dal:table:orders"})
    assert all("via" in item and "relationship" not in item for item in navigation.json()["neighbors"])


def test_search_and_typed_resources_follow_openapi_contract(tmp_path):
    client = api_client(tmp_path)

    response = client.get("/api/v1/search", params={"q": "How many orders?"})
    listing = client.get("/api/v1/resources/table")
    found = client.get(
        "/api/v1/resources/table/" + quote("urn:dal:table:orders", safe=""),
    )

    assert response.status_code == 200
    assert response.json()["estimated_tokens"] <= 1600
    assert response.json()["start_with"] is not None
    assert [item["name"] for item in listing.json()["results"]] == ["customers", "orders"]
    assert found.json()["source"] == "warehouse.orders"


def test_graph_context_is_bounded_and_evidence_is_explicit(tmp_path):
    client = api_client(tmp_path)

    neighbors = client.get(
        "/api/v1/graph/neighbors",
        params={"object_id": "urn:dal:table:orders", "limit": 2},
    )
    evidence = client.get(
        "/api/v1/graph/evidence",
        params={"object_id": "urn:dal:table:orders", "limit": 2},
    )

    assert neighbors.status_code == 200
    assert len(neighbors.json()["neighbors"]) <= 2
    assert all(item["object"] for item in neighbors.json()["neighbors"])
    assert evidence.json() == {"object_id": "urn:dal:table:orders", "evidence": []}


def test_openapi_is_versioned_and_declares_mutation_revision_header(tmp_path):
    schema = api_client(tmp_path).get("/api/v1/openapi.json").json()

    assert schema["info"]["version"] == "1.0.0"
    create = schema["paths"]["/api/v1/proposals"]["post"]
    revision = next(item for item in create["parameters"] if item["name"] == "If-Match")
    assert revision["required"] is True
    assert "/api/v1/proposals/{proposal_id}/deprecate" in schema["paths"]
    assert "/api/v1/search" in schema["paths"]


def test_health_and_revisions_report_current_state(tmp_path):
    client = api_client(tmp_path)

    health = client.get("/api/v1/health")
    revisions = client.get("/api/v1/revisions")

    assert health.status_code == 200
    assert isinstance(health.json()["failures"], list)
    assert revisions.json()["repository"].startswith("sha256:")
    assert revisions.json()["compiled"]
