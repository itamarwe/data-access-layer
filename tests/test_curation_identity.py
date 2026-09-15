"""Distinct public proposal identities must resolve to distinct stored records."""

from dal.curation import CurationService
from dal.repository import encode_document


def test_separator_like_proposal_ids_do_not_alias(tmp_path):
    path = tmp_path / "semantic" / "catalog.yaml"
    path.parent.mkdir()
    path.write_text(encode_document(path, {"version": 1, "objects": [
        {"id": "table:orders", "kind": "table", "name": "orders"},
    ]}))
    service = CurationService(tmp_path)
    identifiers = ("urn:dal:proposal:a:b", "urn:dal:proposal:a--b")
    for identifier in identifiers:
        service.create({
            "id": identifier, "status": "open", "target": {"object_id": "table:orders"},
            "base_revision": service.revision(),
            "patch": [{"op": "add", "path": "/description", "value": identifier}],
        }, expected_revision=service.revision())
    assert [service.get(identifier)["id"] for identifier in identifiers] == list(identifiers)
    assert len(service.list()) == 2
