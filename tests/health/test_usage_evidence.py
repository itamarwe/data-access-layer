from datetime import timedelta

import pytest

from dal.collectors import collect_queries
from dal.collectors.types import claim
from dal.evidence import SnapshotRepository, SourceKind
from dal.health import inspect_health

from .helpers import NOW, authored_repository, request


@pytest.mark.parametrize("separate_snapshots", [False, True])
def test_queries_collected_together_are_not_conflicting_facts(tmp_path, separate_snapshots):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    snapshots = SnapshotRepository(directory)
    result = collect_queries([
        {"QueryExecutionId": "query-1", "sql": "SELECT * FROM sales.orders"},
        {"QueryExecutionId": "query-2", "sql": "SELECT id FROM sales.orders"},
    ], collected_at=NOW)
    assert len(result.evidence) == 2
    if separate_snapshots:
        for record in result.evidence:
            snapshots.put([record])
    else:
        snapshots.put(result.evidence)

    assert inspect_health(request(tmp_path, evidence_directory=directory)).healthy


def test_usage_conflicts_within_one_source_record_are_still_reported(tmp_path):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    SnapshotRepository(directory).put([
        _claim("query-1", "athena:query/query-1"),
        _claim("different-value", "athena:query/query-1"),
        _claim("query-2", "athena:query/query-2"),
    ])

    conflicts = [issue for issue in inspect_health(
        request(tmp_path, evidence_directory=directory),
    ).failures if issue.code == "EVIDENCE_CONFLICT"]
    assert len(conflicts) == 1
    assert conflicts[0].recovery_command


@pytest.mark.parametrize("kind", [SourceKind.DATABASE_SCHEMA, SourceKind.CURATION])
def test_non_usage_conflicts_are_not_hidden_by_distinct_source_uris(tmp_path, kind):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    SnapshotRepository(directory).put([
        _claim("first description", "source:one", kind=kind, path="/description"),
        _claim("different description", "source:two", kind=kind, path="/description"),
    ])

    assert "EVIDENCE_CONFLICT" in {issue.code for issue in inspect_health(
        request(tmp_path, evidence_directory=directory),
    ).failures}


def test_fresh_usage_does_not_make_historical_query_events_stale_failures(tmp_path):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    snapshots = SnapshotRepository(directory)
    snapshots.put([_claim("old-query", "athena:query/old-query", collected_at=NOW - timedelta(days=30))])
    assert "EVIDENCE_STALE" in {issue.code for issue in inspect_health(
        request(tmp_path, evidence_directory=directory),
    ).failures}
    snapshots.put([_claim("new-query", "athena:query/new-query")])

    assert inspect_health(request(tmp_path, evidence_directory=directory)).healthy


def test_newer_value_clears_historical_conflict_for_the_same_source(tmp_path):
    authored_repository(tmp_path)
    directory = tmp_path / "evidence"
    snapshots = SnapshotRepository(directory)
    earlier = NOW - timedelta(days=1)
    snapshots.put([
        _claim("first", "source:one", collected_at=earlier),
        _claim("second", "source:one", collected_at=earlier),
    ])
    snapshots.put([_claim("corrected", "source:one")])

    assert inspect_health(request(tmp_path, evidence_directory=directory)).healthy


def _claim(value, uri, *, kind=SourceKind.QUERY_LOG, path="/usage/query", collected_at=NOW):
    return claim("urn:dal:table:orders", path, value, kind=kind,
                 revision=value, collected_at=collected_at, uri=uri)
