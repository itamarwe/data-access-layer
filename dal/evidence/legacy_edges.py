"""Normalization rules for legacy Legacy relationship evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .legacy_common import ClaimSpec, LegacyRecordFactory, present, relationship_subject
from .model import EvidenceLayer as Layer
from .model import EvidenceRecord, SourceKind as Kind

COLUMN_EDGE_CLAIMS = (
    ClaimSpec("jaccard", "/overlap/jaccard", Layer.PHYSICAL, Kind.DATA_PROFILE, "ratio"),
    ClaimSpec("inter_est", "/overlap/intersection", Layer.PHYSICAL, Kind.DATA_PROFILE, "values"),
    ClaimSpec("card_a", "/overlap/left_cardinality", Layer.PHYSICAL, Kind.DATA_PROFILE, "values"),
    ClaimSpec("card_b", "/overlap/right_cardinality", Layer.PHYSICAL, Kind.DATA_PROFILE, "values"),
    ClaimSpec("cont_a_in_b", "/overlap/left_in_right", Layer.PHYSICAL, Kind.DATA_PROFILE, "ratio"),
    ClaimSpec("cont_b_in_a", "/overlap/right_in_left", Layer.PHYSICAL, Kind.DATA_PROFILE, "ratio"),
    ClaimSpec("max_containment", "/overlap/max_containment", Layer.PHYSICAL, Kind.DATA_PROFILE, "ratio"),
    ClaimSpec("same_family", "/compatible_type", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("name_type_affinity", "/name_type_affinity", Layer.PHYSICAL, Kind.DATA_PROFILE, "ratio"),
    ClaimSpec("observed_usage", "/usage/join_frequency", Layer.USAGE, Kind.QUERY_LOG, "queries"),
    ClaimSpec("observed_count", "/usage/join_count", Layer.USAGE, Kind.QUERY_LOG, "queries"),
    ClaimSpec("observed_key", "/usage/join_expression", Layer.USAGE, Kind.QUERY_LOG),
)

JOIN_EDGE_CLAIM = ClaimSpec(
    "join_count", "/usage/join_count", Layer.USAGE, Kind.QUERY_LOG, "queries",
)


def column_edge_records(
    row: Mapping[str, object], factory: LegacyRecordFactory,
) -> Iterable[EvidenceRecord]:
    subject = relationship_subject(row["col_a"], row["col_b"])
    for spec in COLUMN_EDGE_CLAIMS:
        value = row.get(spec.column)
        if present(value):
            yield factory.record("edges_column", subject, spec, value)


def join_edge_records(
    row: Mapping[str, object], factory: LegacyRecordFactory,
) -> Iterable[EvidenceRecord]:
    left = f"{row['table_a']}.{row['col_a']}"
    right = f"{row['table_b']}.{row['col_b']}"
    subject = relationship_subject(left, right)
    value = row.get("join_count")
    if present(value):
        yield factory.record("edges_join", subject, JOIN_EDGE_CLAIM, value)
