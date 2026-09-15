"""Paired comparisons for proposed context-layer additions."""

from __future__ import annotations

from dataclasses import dataclass

from .model import EvaluationRun


@dataclass(frozen=True)
class AblationComparison:
    baseline: str
    candidate: str
    paired_cases: int
    success_at_budget_delta: float
    success_delta: float
    mean_turn_delta: float
    mean_token_delta: float
    mean_latency_ms_delta: float
    improved_cases: tuple[str, ...]
    regressed_cases: tuple[str, ...]

    @property
    def adds_value(self) -> bool:
        cost_deltas = (
            self.mean_turn_delta, self.mean_token_delta, self.mean_latency_ms_delta,
        )
        lower_cost = all(value <= 0 for value in cost_deltas) and any(
            value < 0 for value in cost_deltas
        )
        advances_frontier = self.success_at_budget_delta > 0 or (
            self.success_at_budget_delta == 0
            and self.success_delta >= 0
            and lower_cost
        )
        return advances_frontier and not self.regressed_cases


def compare_variants(
    baseline: EvaluationRun, candidate: EvaluationRun,
) -> AblationComparison:
    """Compare the same cases; reject incomparable evaluation runs."""
    before = {item.case_id: item for item in baseline.results}
    after = {item.case_id: item for item in candidate.results}
    if set(before) != set(after):
        raise ValueError("ablation variants must contain the same case IDs")
    improved = tuple(sorted(
        case_id for case_id in before
        if not before[case_id].success_at_budget and after[case_id].success_at_budget
    ))
    regressed = tuple(sorted(
        case_id for case_id in before
        if before[case_id].success_at_budget and not after[case_id].success_at_budget
    ))
    return AblationComparison(
        baseline=baseline.variant,
        candidate=candidate.variant,
        paired_cases=len(before),
        success_at_budget_delta=(
            candidate.summary.success_at_budget_rate
            - baseline.summary.success_at_budget_rate
        ),
        success_delta=candidate.summary.success_rate - baseline.summary.success_rate,
        mean_turn_delta=candidate.summary.mean_turns - baseline.summary.mean_turns,
        mean_token_delta=candidate.summary.mean_tokens - baseline.summary.mean_tokens,
        mean_latency_ms_delta=(
            candidate.summary.mean_latency_ms - baseline.summary.mean_latency_ms
        ),
        improved_cases=improved,
        regressed_cases=regressed,
    )
