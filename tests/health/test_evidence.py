from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace

from dal.evidence import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource,
    SnapshotRepository, SourceKind,
)
from dal.health import inspect_health

from .helpers import authored_repository, request, NOW


def test_fresh_source_claim_replaces_old_health_failure_without_deleting_history(tmp_path):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    snapshots = SnapshotRepository(directory)
    record = _old_record()
    snapshots.put([record])
    snapshots.put([replace(record, collected_at=NOW)])
    result = inspect_health(request(tmp_path, evidence_directory=directory))
    assert result.healthy
    assert len(list(directory.glob("*.json"))) == 2


def test_source_corruption_has_a_recovery_and_new_measurement_can_clear_it(tmp_path):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    snapshots = SnapshotRepository(directory)
    corrupt = replace(_old_record(), claim_path="/corrupt",
                      claim_value={"corrupt": True, "reason": "Invalid file"}, collected_at=NOW)
    snapshots.put([corrupt])
    assert "SOURCE_CORRUPT" in {item.code for item in inspect_health(request(tmp_path, evidence_directory=directory)).failures}


def test_stale_and_corrupt_evidence_snapshots_are_failures(tmp_path):
    authored_repository(tmp_path)
    directory = tmp_path / ".dal" / "snapshots"
    SnapshotRepository(directory).put([_old_record()])
    (directory / "bad.json").write_text("not-json", encoding="utf-8")

    result = inspect_health(request(tmp_path, evidence_directory=directory))
    by_code = {item.code: item for item in result.failures}

    assert {"EVIDENCE_STALE", "EVIDENCE_SNAPSHOT_CORRUPT"} <= set(by_code)
    assert by_code["EVIDENCE_STALE"].recovery_command == "dal build --help"


def test_missing_configured_evidence_directory_is_a_failure(tmp_path):
    authored_repository(tmp_path)

    result = inspect_health(request(
        tmp_path, evidence_directory=tmp_path / "missing-snapshots",
    ))

    assert "EVIDENCE_DIRECTORY_MISSING" in {item.code for item in result.failures}


def _old_record() -> EvidenceRecord:
    return EvidenceRecord(
        record_id="urn:dal:evidence:old-usage",
        layer=EvidenceLayer.USAGE,
        subject_id="urn:dal:table:orders",
        claim_path="/joins",
        claim_value=3,
        source=EvidenceSource(SourceKind.QUERY_LOG, "log-1"),
        collected_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        content=ContentReference("query-log:one", "a" * 64),
    )
