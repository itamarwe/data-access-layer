import json
from datetime import datetime, timezone

import pytest

from dal.compiler import BundleBuilder
from dal.compiler.evidence_reader import snapshot_records
from dal.evidence import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource, SourceKind,
    SnapshotCollisionError, SnapshotRepository, deserialize_snapshot, serialize_snapshot,
)


def record():
    return EvidenceRecord("e1", EvidenceLayer.PHYSICAL, "table:orders", "/exists", True,
                          EvidenceSource(SourceKind.DATABASE_SCHEMA, "v1"),
                          datetime(2026, 9, 14, tzinfo=timezone.utc),
                          ContentReference("source:orders", "a" * 64))


@pytest.mark.parametrize("payload", [
    b'{"format":"other","records":[]}',
    b'{"records":[]}',
    b'{"format":"dal.evidence.v1","records":{}}',
    b'{"format":"dal.evidence.v1","records":[]} garbage',
    b'{"format":"dal.evidence.v1","records":[],"records":[]}',
    b'{"format":"dal.evidence.v1","records":[{},]}',
    b'{"format":"dal.evidence.v1","records":[42]}',
    b'{"format":"dal.evidence.v1","records":[],}',
])
def test_bad_envelope_rejected_by_both_readers(tmp_path, payload):
    path = tmp_path / "evidence.json"
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        deserialize_snapshot(payload)
    with pytest.raises(ValueError):
        list(snapshot_records(path))


def test_whitespace_and_property_order_are_irrelevant(tmp_path):
    document = json.loads(serialize_snapshot([record()]))
    payload = json.dumps({"records": document["records"], "format": document["format"]}, indent=2).encode()
    path = tmp_path / "evidence.json"
    path.write_bytes(payload)
    assert deserialize_snapshot(payload) == (record(),)
    assert len(list(snapshot_records(path))) == 1


@pytest.mark.parametrize("change", [
    {"collected_at": "2026-09-14T12:00:00"},
    {"strength": 2}, {"strength": True},
    {"content": {"uri": "x", "sha256": "../invalid"}},
    {"measurement": {"unit": "rows"}},
])
def test_invalid_record_fields_fail(change):
    document = json.loads(serialize_snapshot([record()]))
    document["records"][0].update(change)
    with pytest.raises(ValueError):
        deserialize_snapshot(json.dumps(document).encode())


def test_duplicate_record_ids_fail_on_read_and_write():
    document = json.loads(serialize_snapshot([record()]))
    document["records"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        deserialize_snapshot(json.dumps(document).encode())
    with pytest.raises(ValueError, match="duplicate"):
        serialize_snapshot([record(), record()])


def test_snapshot_get_rejects_traversal_and_tampering(tmp_path):
    repository = SnapshotRepository(tmp_path)
    with pytest.raises(ValueError):
        repository.get("../other")
    stored = repository.put([record()])
    stored.path.chmod(0o644)
    stored.path.write_bytes(b"{}")
    with pytest.raises(SnapshotCollisionError):
        repository.get(stored.snapshot_id)


def test_invalid_snapshot_never_replaces_active_bundle(tmp_path):
    document = {"version": 1, "objects": [{"id": "table:orders", "kind": "table", "name": "orders"}]}
    root = tmp_path / "bundle"
    first = BundleBuilder(root).build(document)
    active = (root / "active.json").read_bytes()
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(serialize_snapshot([record()]) + b"garbage")
    with pytest.raises(ValueError):
        BundleBuilder(root).build(document, invalid)
    assert (root / "active.json").read_bytes() == active
    assert first.bundle.is_dir()
