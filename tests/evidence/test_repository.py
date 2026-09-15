"""Content addressing and immutable publication tests."""

from datetime import datetime, timezone

import pytest

from dal.evidence import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource,
    Measurement, SnapshotCollisionError, SnapshotRepository, SourceKind,
    serialize_snapshot, snapshot_id,
)


def test_serialization_is_deterministic_and_round_trips(tmp_path):
    records = (_record("b", 2), _record("a", "one row per order", measured=False))

    assert serialize_snapshot(records) == serialize_snapshot(reversed(records))
    repository = SnapshotRepository(tmp_path)
    stored = repository.put(records)
    assert stored.snapshot_id == snapshot_id(stored.path.read_bytes())
    assert repository.get(stored.snapshot_id) == tuple(reversed(records))
    assert repository.get(stored.snapshot_id)[0].claim_value == "one row per order"
    assert repository.get(stored.snapshot_id)[1].measurement.value == 2
    assert stored.path.stat().st_mode & 0o222 == 0


def test_republishing_never_replaces_the_snapshot_file(tmp_path):
    repository = SnapshotRepository(tmp_path)
    stored = repository.put([_record("a", 1)])
    inode = stored.path.stat().st_ino

    repeated = repository.put([_record("a", 1)])

    assert repeated.path.stat().st_ino == inode


def test_existing_wrong_content_is_reported_not_overwritten(tmp_path):
    record = _record("a", 1)
    payload = serialize_snapshot([record])
    identifier = snapshot_id(payload)
    target = tmp_path / f"{identifier}.json"
    target.write_bytes(b"wrong")

    with pytest.raises(SnapshotCollisionError):
        SnapshotRepository(tmp_path).put([record])
    assert target.read_bytes() == b"wrong"


def test_naive_collection_time_is_rejected_at_serialization():
    record = _record("a", 1)
    record = EvidenceRecord(**{
        **record.__dict__, "collected_at": datetime(2026, 1, 1),
    })

    with pytest.raises(ValueError, match="timezone"):
        serialize_snapshot([record])


def _record(suffix: str, value: object, measured: bool = True) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=f"urn:dal:evidence:{suffix}",
        layer=EvidenceLayer.PHYSICAL,
        subject_id="table:orders",
        claim_path=f"/claim/{suffix}",
        claim_value=value,
        source=EvidenceSource(SourceKind.DATA_PROFILE, "capture-1"),
        collected_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        content=ContentReference(f"capture:{suffix}", suffix * 64),
        measurement=Measurement.from_json(value, "rows") if measured else None,
    )
