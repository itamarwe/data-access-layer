"""Integrity and age of the latest source claims; historical snapshots remain evidence."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

from dal.evidence import deserialize_snapshot, snapshot_id
from .model import HealthIssue


def inspect_evidence(directory: Path, now: datetime, maximum_age: timedelta) -> list[HealthIssue]:
    if not directory.exists():
        return [HealthIssue("EVIDENCE_DIRECTORY_MISSING", str(directory),
            "The configured evidence snapshot directory does not exist.", "dal build --help")]
    failures, latest = [], {}
    for path in sorted(directory.glob("*.json")):
        try:
            payload = path.read_bytes()
            if path.stem != snapshot_id(payload):
                raise ValueError("snapshot filename does not match its content digest")
            records = deserialize_snapshot(payload)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, OverflowError) as error:
            failures.append(HealthIssue("EVIDENCE_SNAPSHOT_CORRUPT", str(path), str(error), "dal build --help"))
            continue
        for record in records:
            key = (record.layer, record.subject_id, record.claim_path, record.source.kind)
            previous = latest.get(key)
            if previous is None or record.collected_at > previous.collected_at:
                latest[key] = record
            elif record.collected_at == previous.collected_at and record.claim_value != previous.claim_value:
                failures.append(HealthIssue("EVIDENCE_CONFLICT", record.subject_id,
                    f"Different source values at the same time for {record.claim_path}.",
                    "Inspect the source records and collect a corrected snapshot."))
    stale = defaultdict(int)
    for record in latest.values():
        claim = record.claim_value
        if record.claim_path == "/corrupt" and isinstance(claim, Mapping) and claim.get("corrupt") is True:
            failures.append(HealthIssue("SOURCE_CORRUPT", record.subject_id,
                str(claim.get("reason", "Source data was reported corrupt.")),
                "Repair upstream source data, then collect a new snapshot and run dal build."))
        if now - record.collected_at > maximum_age:
            stale[(record.subject_id, record.layer.value)] += 1
    for (subject, layer), count in sorted(stale.items()):
        failures.append(HealthIssue("EVIDENCE_STALE", subject,
            f"{count} latest {layer} claims exceed the configured evidence age threshold.",
            "dal proposal list --status open" if layer == "curation" else "dal build --help"))
    return failures
