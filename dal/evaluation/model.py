"""Explicit inputs and outputs for context retrieval evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    expected_object_ids: frozenset[str]
    max_turns: int
    max_tokens: int
    category: str = "retrieval"
    source_refs: tuple[str, ...] = ()
    evaluable: bool = True
    not_evaluable_reason: str | None = None
    max_latency_ms: float | None = None
    retrieval_queries: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not isinstance(query, str) or not query.strip() for query in self.retrieval_queries):
            raise ValueError("retrieval queries must be nonempty strings")
        if not self.case_id or not self.category:
            raise ValueError("evaluation case identity and category are required")
        if self.max_turns < 1 or self.max_tokens < 1:
            raise ValueError("evaluation budgets must be positive")
        if self.max_latency_ms is not None and self.max_latency_ms < 0:
            raise ValueError("evaluation latency budget cannot be negative")
        if self.evaluable == (self.not_evaluable_reason is not None):
            raise ValueError("only non-evaluable cases require a reason")


@dataclass(frozen=True)
class SearchObservation:
    returned_object_ids: tuple[str, ...]
    turns: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    embedding_available: bool = True
    degradation_reason: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __post_init__(self) -> None:
        measurements = (
            self.turns, self.input_tokens, self.output_tokens, self.latency_ms,
        )
        if any(value < 0 for value in measurements):
            raise ValueError("evaluation measurements cannot be negative")
        if self.embedding_available and self.degradation_reason is not None:
            raise ValueError("available embeddings cannot have a degradation reason")


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    success: bool
    within_budget: bool
    recall: float
    turns: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    embedding_available: bool
    degradation_reason: str | None

    @property
    def success_at_budget(self) -> bool:
        return self.success and self.within_budget


@dataclass(frozen=True)
class EvaluationSummary:
    cases: int
    success_rate: float
    success_at_budget_rate: float
    mean_recall: float
    mean_turns: float
    mean_input_tokens: float
    mean_output_tokens: float
    mean_tokens: float
    mean_latency_ms: float
    p95_latency_ms: float
    degraded_search_rate: float


@dataclass(frozen=True)
class EvaluationRun:
    variant: str
    results: tuple[CaseResult, ...]
    summary: EvaluationSummary
    evaluation_type: str = "retrieval_regression"
