"""Evidence records, snapshots, and legacy extraction."""

from .legacy import LegacyEvidenceExtractor
from .model import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource,
    Measurement, SourceKind, content_digest, stable_record_id,
)
from .repository import SnapshotCollisionError, SnapshotRepository, StoredSnapshot
from .serialization import deserialize_snapshot, serialize_snapshot, snapshot_id

__all__ = (
    "LegacyEvidenceExtractor",
    "ContentReference",
    "EvidenceLayer",
    "EvidenceRecord",
    "EvidenceSource",
    "Measurement",
    "SnapshotCollisionError",
    "SnapshotRepository",
    "SourceKind",
    "StoredSnapshot",
    "content_digest",
    "deserialize_snapshot",
    "serialize_snapshot",
    "snapshot_id",
    "stable_record_id",
)
