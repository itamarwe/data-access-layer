"""Evidence values remain queryable in the compiled bundle."""

import json
from datetime import datetime, timezone

import duckdb

from dal.compiler import BundleBuilder
from dal.evidence import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource, SourceKind,
)

from .fixtures import native_document


def test_compiles_complete_evidence_payload(tmp_path):
    evidence = EvidenceRecord(
        record_id="urn:dal:evidence:orders-description",
        layer=EvidenceLayer.CURATION,
        subject_id="table:orders",
        claim_path="/description",
        claim_value="Approved order records",
        source=EvidenceSource(SourceKind.CURATION, "git:abc123"),
        collected_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        content=ContentReference("curation:orders", "a" * 64),
    )

    result = BundleBuilder(tmp_path / "bundle").build(
        native_document(), [evidence],
    )

    connection = duckdb.connect(str(result.bundle / "catalog.duckdb"), read_only=True)
    try:
        payload = connection.execute(
            "SELECT payload FROM evidence WHERE id = ?", [evidence.record_id],
        ).fetchone()[0]
    finally:
        connection.close()
    assert json.loads(payload)["claim_value"] == "Approved order records"
