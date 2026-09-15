"""Values returned after successful curation mutations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurationResult:
    proposal: dict[str, object]
    repository_revision: str
