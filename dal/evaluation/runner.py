"""Run deterministic retrieval cases against any search adapter."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable

from .model import (
    CaseResult, EvaluationCase, EvaluationRun, EvaluationSummary,
    SearchObservation,
)

Search = Callable[[EvaluationCase], SearchObservation]


def evaluate(
    variant: str, cases: Iterable[EvaluationCase], search: Search,
) -> EvaluationRun:
    """Score retrieval regression only; presence of an ID is not query correctness."""
    materialized = tuple(cases)
    identifiers = [case.case_id for case in materialized]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("evaluation case IDs must be unique")
    blocked = [case.case_id for case in materialized if not case.evaluable]
    if blocked:
        raise ValueError(f"evaluation cases are not evaluable: {', '.join(blocked)}")
    results = tuple(_score(case, search(case)) for case in materialized)
    return EvaluationRun(variant, results, _summarize(results))


def _score(case: EvaluationCase, observed: SearchObservation) -> CaseResult:
    expected = case.expected_object_ids
    returned = set(observed.returned_object_ids)
    found = len(expected.intersection(returned))
    recall = found / len(expected) if expected else 1.0
    success = expected.issubset(returned) if expected else not returned
    within_budget = (
        observed.turns <= case.max_turns
        and observed.total_tokens <= case.max_tokens
        and (
            case.max_latency_ms is None
            or observed.latency_ms <= case.max_latency_ms
        )
    )
    return CaseResult(
        case_id=case.case_id, success=success, within_budget=within_budget,
        recall=recall, turns=observed.turns,
        input_tokens=observed.input_tokens, output_tokens=observed.output_tokens,
        total_tokens=observed.total_tokens, latency_ms=observed.latency_ms,
        embedding_available=observed.embedding_available,
        degradation_reason=observed.degradation_reason,
    )


def _summarize(results: tuple[CaseResult, ...]) -> EvaluationSummary:
    count = len(results)
    if not count:
        return EvaluationSummary(
            0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        )
    return EvaluationSummary(
        cases=count,
        success_rate=sum(item.success for item in results) / count,
        success_at_budget_rate=sum(item.success_at_budget for item in results) / count,
        mean_recall=sum(item.recall for item in results) / count,
        mean_turns=sum(item.turns for item in results) / count,
        mean_input_tokens=sum(item.input_tokens for item in results) / count,
        mean_output_tokens=sum(item.output_tokens for item in results) / count,
        mean_tokens=sum(item.total_tokens for item in results) / count,
        mean_latency_ms=sum(item.latency_ms for item in results) / count,
        p95_latency_ms=_percentile(tuple(item.latency_ms for item in results), 0.95),
        degraded_search_rate=sum(not item.embedding_available for item in results) / count,
    )


def _percentile(values: tuple[float, ...], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]
