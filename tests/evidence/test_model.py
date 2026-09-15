"""Contracts for the deliberately small evidence vocabulary."""

from datetime import datetime, timezone

from dal.evidence import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource, SourceKind,
    stable_record_id,
)


def test_model_has_exactly_three_layers():
    assert {layer.value for layer in EvidenceLayer} == {
        "physical", "usage", "curation",
    }


def test_usage_sources_cover_supported_organizational_inputs():
    assert {
        SourceKind.QUERY_LOG,
        SourceKind.LINEAGE,
        SourceKind.DASHBOARD,
        SourceKind.REPORT,
        SourceKind.ORGANIZATIONAL_COMMUNICATION,
    } <= set(SourceKind)


def test_record_identity_is_stable_and_content_sensitive():
    source = EvidenceSource(SourceKind.DATA_PROFILE, "snapshot-7")
    content = ContentReference("capture:rows", "a" * 64)
    first = stable_record_id(
        EvidenceLayer.PHYSICAL, "table:orders", "/row_count", source, content,
    )
    second = stable_record_id(
        EvidenceLayer.PHYSICAL, "table:orders", "/row_count", source, content,
    )
    changed = stable_record_id(
        EvidenceLayer.PHYSICAL,
        "table:orders",
        "/row_count",
        source,
        ContentReference("capture:rows", "b" * 64),
    )

    assert first == second
    assert first != changed
    assert first.startswith("urn:dal:evidence:")


def test_claim_values_are_copied_into_immutable_containers():
    source_value = {"terms": ["orders", "bookings"]}
    record = EvidenceRecord(
        record_id="urn:dal:evidence:context",
        layer=EvidenceLayer.CURATION,
        subject_id="table:orders",
        claim_path="/description",
        claim_value=source_value,
        source=EvidenceSource(SourceKind.CURATION, "revision"),
        collected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        content=ContentReference("curation:orders", "a" * 64),
    )
    source_value["terms"].append("purchases")

    assert record.claim_value["terms"] == ("orders", "bookings")
