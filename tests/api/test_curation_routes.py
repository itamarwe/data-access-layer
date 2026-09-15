from fastapi.testclient import TestClient

from dal.api import ServerConfig, create_app
from dal.compiler import BundleBuilder
from tests.application.fixtures import native_document
from tests.curation.helpers import proposal, repository


def _client(root):
    repository(root)
    bundle = root / ".dal" / "query"
    BundleBuilder(bundle).build(native_document())
    return TestClient(create_app(ServerConfig(root, bundle)))


def test_create_publish_and_dismiss_are_routed_through_revision_checks(tmp_path):
    client = _client(tmp_path)
    revision = client.get("/api/v1/revisions").json()["repository"]
    change = proposal(tmp_path)

    created = client.post(
        "/api/v1/proposals", json={"proposal": change}, headers={"If-Match": revision},
    )
    assert created.status_code == 201
    next_revision = created.json()["repository_revision"]

    published = client.post(
        f"/api/v1/proposals/{change['id']}/publish",
        json={"decided_by": "user:curator", "reason": "Checked against the source."},
        headers={"If-Match": next_revision},
    )
    assert published.status_code == 200
    assert published.json()["proposal"]["status"] == "published"

    other = proposal(tmp_path, proposal_id="urn:dal:proposal:dismiss-me")
    current = published.json()["repository_revision"]
    made = client.post(
        "/api/v1/proposals", json={"proposal": other}, headers={"If-Match": current},
    ).json()
    dismissed = client.post(
        f"/api/v1/proposals/{other['id']}/dismiss", json={"reason": "Not supported."},
        headers={"If-Match": made["repository_revision"]},
    )
    assert dismissed.json()["proposal"]["status"] == "dismissed"


def test_mutations_require_current_if_match(tmp_path):
    client = _client(tmp_path)
    change = proposal(tmp_path)

    assert client.post("/api/v1/proposals", json={"proposal": change}).status_code == 422
    conflict = client.post(
        "/api/v1/proposals", json={"proposal": change}, headers={"If-Match": "sha256:stale"},
    )
    assert conflict.status_code == 409
    assert client.get("/api/v1/proposals").json() == []


def test_deprecate_uses_the_same_revision_checked_service_path(tmp_path):
    repository(tmp_path, published_table=True)
    bundle = tmp_path / ".dal" / "query"
    BundleBuilder(bundle).build(native_document())
    client = TestClient(create_app(ServerConfig(tmp_path, bundle)))
    revision = client.get("/api/v1/revisions").json()["repository"]
    change = proposal(tmp_path, proposal_id="urn:dal:proposal:deprecate-api", patch=[{
        "op": "replace",
        "path": "/status",
        "value": "deprecated",
    }])

    created = client.post(
        "/api/v1/proposals", json={"proposal": change}, headers={"If-Match": revision},
    ).json()
    response = client.post(
        f"/api/v1/proposals/{change['id']}/deprecate", json={},
        headers={"If-Match": created["repository_revision"]},
    )

    assert response.status_code == 200
    assert response.json()["proposal"]["status"] == "published"


def test_create_new_doctrine_uses_the_same_proposal_lifecycle(tmp_path):
    client = _client(tmp_path)
    revision = client.get("/api/v1/revisions").json()["repository"]
    change = {
        "id": "urn:dal:proposal:new-method", "status": "open", "base_revision": revision,
        "target": {"object_id": "urn:dal:doctrine:refunds"},
        "object": {"id": "urn:dal:doctrine:refunds", "kind": "doctrine", "name": "Refunds",
                   "content": "Exclude pending refunds from settled revenue."},
    }
    created = client.post("/api/v1/proposals", json={"proposal": change}, headers={"If-Match": revision})
    assert created.status_code == 201
    published = client.post(f"/api/v1/proposals/{change['id']}/publish", json={},
                            headers={"If-Match": created.json()["repository_revision"]})
    assert published.status_code == 200
