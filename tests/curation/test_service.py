from copy import deepcopy

import pytest

from dal.curation import CurationService, CurationError
from dal.repository import read_document, encode_document, repository_revision, RevisionConflict
from .helpers import repository, proposal, proposal_path, TABLE_ID


def resource(path):
    return next(obj for obj in read_document(path)["objects"] if obj["id"] == TABLE_ID)


def edit(path, **updates):
    document = read_document(path)
    next(obj for obj in document["objects"] if obj["id"] == TABLE_ID).update(updates)
    path.write_text(encode_document(path, document))


def create(root, **kwargs):
    service = CurationService(root)
    item = proposal(root, **kwargs)
    service.create(item, expected_revision=service.revision())
    return service, item


def test_proposal_is_not_canonical_until_published(tmp_path):
    path = repository(tmp_path)
    before = path.read_bytes()
    service, item = create(tmp_path)
    assert path.read_bytes() == before
    result = service.publish(item["id"], expected_revision=service.revision(), decided_by="curator:one")
    assert resource(path)["description"] == "Published order facts."
    assert result.proposal["status"] == "published"
    with pytest.raises(CurationError, match="already published"):
        service.publish(item["id"], expected_revision=service.revision())


def test_same_field_direct_edit_blocks_old_proposal_even_with_current_revision(tmp_path):
    path = repository(tmp_path)
    service, item = create(tmp_path)
    edit(path, description="New direct edit")
    with pytest.raises(CurationError, match="fields changed"):
        service.publish(item["id"], expected_revision=service.revision())
    assert resource(path)["description"] == "New direct edit"
    assert service.get(item["id"])["status"] == "open"


def test_unrelated_edit_array_reorder_and_file_move_do_not_break_identity(tmp_path):
    path = repository(tmp_path)
    service, item = create(tmp_path)
    edit(path, grain={"description": "one row per order"})
    document = read_document(path)
    document["objects"].reverse()
    moved = path.with_name("moved.yaml")
    moved.write_text(encode_document(moved, document))
    path.unlink()
    service.publish(item["id"], expected_revision=service.revision())
    assert resource(moved)["grain"] == {"description": "one row per order"}
    assert resource(moved)["description"] == "Published order facts."


def test_stale_expected_revision_never_writes(tmp_path):
    path = repository(tmp_path)
    service, item = create(tmp_path)
    before = service.revision()
    edit(path, owner="someone")
    with pytest.raises(RevisionConflict):
        service.publish(item["id"], expected_revision=before)


def test_dismiss_does_not_change_resource(tmp_path):
    path = repository(tmp_path)
    before = path.read_bytes()
    service, item = create(tmp_path)
    result = service.dismiss(item["id"], expected_revision=service.revision())
    assert result.proposal["status"] == "dismissed"
    assert path.read_bytes() == before


def test_deprecation_is_explicit_and_retains_published_proposal(tmp_path):
    path = repository(tmp_path)
    service, item = create(tmp_path, patch=[{"op": "add", "path": "/status", "value": "deprecated"}])
    with pytest.raises(CurationError, match="use deprecate"):
        service.publish(item["id"], expected_revision=service.revision())
    service.deprecate(item["id"], expected_revision=service.revision())
    assert resource(path)["status"] == "deprecated"
    assert service.get(item["id"])["status"] == "published"


@pytest.mark.parametrize("path", ["/id", "/kind", "/objects/0/name", "/aliases/0"])
def test_identity_or_position_patches_rejected(tmp_path, path):
    repository(tmp_path)
    with pytest.raises(CurationError):
        create(tmp_path, patch=[{"op": "add", "path": path, "value": "changed"}])


def test_validation_spans_multiple_resource_files(tmp_path):
    path = repository(tmp_path)
    document = read_document(path)
    tables = [item for item in document["objects"] if item["kind"] == "table"]
    rest = [item for item in document["objects"] if item["kind"] != "table"]
    path.write_text(encode_document(path, {"version": 1, "objects": tables}))
    related = path.with_name("related.yaml")
    related.write_text(encode_document(related, {"version": 1, "objects": rest}))
    service, item = create(tmp_path)
    service.publish(item["id"], expected_revision=service.revision())
    assert resource(path)["description"] == "Published order facts."


def test_create_resource_uses_same_proposal_lifecycle(tmp_path):
    service = CurationService(tmp_path)
    item = {"id": "urn:dal:proposal:new", "status": "open", "base_revision": service.revision(),
            "target": {"object_id": "table:new"},
            "object": {"id": "table:new", "kind": "table", "name": "new"}}
    service.create(item, expected_revision=service.revision())
    assert not (tmp_path / "semantic" / "catalog.yaml").exists()
    service.publish(item["id"], expected_revision=service.revision())
    created = read_document(tmp_path / "semantic" / "catalog.yaml")["objects"][0]
    assert {key: created[key] for key in item["object"]} == item["object"]
    assert "name" in created["curation"]["fields"]


def test_unresolved_reference_never_publishes(tmp_path):
    repository(tmp_path)
    with pytest.raises(CurationError, match="reference"):
        create(tmp_path, patch=[{"op": "add", "path": "/object_ids", "value": ["table:missing"]}])


def test_published_source_field_is_protected_during_refresh(tmp_path):
    from dal.collectors import refresh_document
    path = repository(tmp_path)
    service, item = create(tmp_path, patch=[{"op": "add", "path": "/source", "value": "curated.orders"}])
    service.publish(item["id"], expected_revision=service.revision())
    refreshed = refresh_document(read_document(path), [
        {"id": TABLE_ID, "kind": "table", "name": "orders", "source": "physical.orders"},
    ])
    current = next(item for item in refreshed["objects"] if item["id"] == TABLE_ID)
    assert current["source"] == "curated.orders"
    assert "source" in current["curation"]["fields"]
