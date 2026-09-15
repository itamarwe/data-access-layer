"""Stable application-facing catalog and search values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import math


@dataclass(frozen=True)
class CatalogObject:
    id: str
    kind: str
    name: str
    parent_id: str | None
    source: str | None
    payload: Mapping[str, object]


@dataclass(frozen=True)
class ObjectSummary:
    id: str
    kind: str
    name: str
    description: str | None = None


@dataclass(frozen=True)
class RankingSignals:
    lexical: float
    embedding: float
    graph: float
    evidence: float
    publication: float


@dataclass(frozen=True)
class SearchResult:
    object: ObjectSummary
    score: float
    signals: RankingSignals
    source: str | None = None
    parent_id: str | None = None
    grain: object | None = None
    publication: str | None = None
    details: Mapping[str, object] | None = None


@dataclass(frozen=True)
class CompactMatch:
    id: str
    kind: str
    name: str
    score: float


@dataclass(frozen=True)
class GraphNeighbor:
    via: str
    object: ObjectSummary | None


@dataclass(frozen=True)
class Connection:
    id: str
    name: str
    source_id: str
    target_id: str
    details: Mapping[str, object] | None = None


@dataclass(frozen=True)
class Connections:
    relations: tuple[Connection, ...] = ()
    joins: tuple[Connection, ...] = ()
    mappings: tuple[Connection, ...] = ()


@dataclass(frozen=True)
class EvidenceSummary:
    id: str
    layer: str
    subject_id: str
    claim_path: str
    source_kind: str
    strength: float | None
    claim_value: object = None
    collected_at: str | None = None
    source_revision: str | None = None
    content: object = None
    measurement: object = None


@dataclass(frozen=True)
class Gap:
    code: str
    object_id: str
    message: str


@dataclass(frozen=True)
class StartWith:
    object_id: str
    reason: str


@dataclass(frozen=True)
class NextCommand:
    command: str
    purpose: str


@dataclass(frozen=True)
class Omissions:
    total_matches: int
    detailed: int
    compact: int
    omitted: int


@dataclass(frozen=True)
class SearchCapabilities:
    lexical: str
    embedding: str
    embedding_reason: str | None = None


@dataclass(frozen=True)
class RankingWeights:
    lexical: float = 0.55
    embedding: float = 0.20
    graph: float = 0.10
    evidence: float = 0.10
    publication: float = 0.05

    def override(self, values: Mapping[str, float] | None) -> "RankingWeights":
        if not values:
            return self
        current = self.as_dict()
        unknown = set(values) - set(current)
        if unknown:
            raise ValueError(f"unknown ranking weights: {', '.join(sorted(unknown))}")
        if any(not math.isfinite(value) or value < 0 for value in values.values()):
            raise ValueError("ranking weights must be finite and nonnegative")
        current.update(values)
        total = sum(current.values())
        if total <= 0:
            raise ValueError("at least one ranking weight must be positive")
        return RankingWeights(**{key: value / total for key, value in current.items()})

    def as_dict(self) -> dict[str, float]:
        return {
            "lexical": self.lexical,
            "embedding": self.embedding,
            "graph": self.graph,
            "evidence": self.evidence,
            "publication": self.publication,
        }


@dataclass(frozen=True)
class SearchResponse:
    query: str
    read_as: str
    start_with: StartWith | None
    results: tuple[SearchResult, ...]
    also_matched: tuple[CompactMatch, ...]
    connections: Connections
    evidence: tuple[EvidenceSummary, ...]
    relevant_doctrine: ObjectSummary | None
    relevant_gold_query: ObjectSummary | None
    gaps: tuple[Gap, ...]
    omissions: Omissions
    estimated_tokens: int
    next_commands: tuple[NextCommand, ...]
    ranking_weights: RankingWeights
    capabilities: SearchCapabilities


@dataclass(frozen=True)
class SearchOptions:
    max_details: int = 6
    max_compact: int = 6
    max_connections: int = 6
    max_evidence: int = 6
    candidate_limit: int = 100
    token_budget: int = 1_600
    include_deprecated: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.max_details <= 20:
            raise ValueError("max_details must be between one and twenty")
        if self.token_budget < 400:
            raise ValueError("minimum supported token budget is 400 estimated tokens")
        positive = (self.candidate_limit, self.token_budget)
        nonnegative = (self.max_compact, self.max_connections, self.max_evidence)
        if any(value <= 0 for value in positive) or any(value < 0 for value in nonnegative):
            raise ValueError("search limits are invalid")
