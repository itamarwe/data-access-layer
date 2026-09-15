"""A collector returns objects and evidence; persistence belongs to the caller."""

from dataclasses import dataclass
from datetime import datetime

from dal.evidence import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource, Measurement,
    SourceKind, content_digest, stable_record_id,
)


@dataclass(frozen=True)
class CollectionResult:
    objects: tuple[dict, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[str, ...] = ()


def claim(subject, path, value, *, kind: SourceKind, revision: str, collected_at: datetime,
          uri: str, unit: str | None = None):
    layer = (EvidenceLayer.CURATION if kind is SourceKind.CURATION else
             EvidenceLayer.PHYSICAL if kind in {SourceKind.DATABASE_SCHEMA, SourceKind.DATA_PROFILE} else EvidenceLayer.USAGE)
    source = EvidenceSource(kind, revision)
    content = ContentReference(uri, content_digest(value))
    return EvidenceRecord(
        stable_record_id(layer, subject, path, source, content), layer, subject, path, value,
        source, collected_at, content, measurement=Measurement(value, unit) if unit else None,
    )
