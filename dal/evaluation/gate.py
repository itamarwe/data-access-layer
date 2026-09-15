"""Configurable release criteria for a benchmark run."""

from __future__ import annotations

from dataclasses import dataclass

from .model import EvaluationRun


@dataclass(frozen=True)
class QualityGate:
    minimum_success_at_budget_rate: float = 1.0
    minimum_mean_recall: float = 1.0
    maximum_mean_turns: float | None = None
    maximum_mean_tokens: float | None = None
    maximum_p95_latency_ms: float | None = None

    def __post_init__(self) -> None:
        rates = (self.minimum_success_at_budget_rate, self.minimum_mean_recall)
        limits = (
            self.maximum_mean_turns, self.maximum_mean_tokens,
            self.maximum_p95_latency_ms,
        )
        if any(not 0 <= value <= 1 for value in rates):
            raise ValueError("quality-gate rates must be between zero and one")
        if any(value is not None and value < 0 for value in limits):
            raise ValueError("quality-gate limits cannot be negative")


@dataclass(frozen=True)
class GateAssessment:
    failures: tuple[str, ...]

    @property
    def meets_gate(self) -> bool:
        return not self.failures


def assess_gate(run: EvaluationRun, gate: QualityGate) -> GateAssessment:
    summary = run.summary
    failures = []
    if summary.success_at_budget_rate < gate.minimum_success_at_budget_rate:
        failures.append("success_at_budget_rate")
    if summary.mean_recall < gate.minimum_mean_recall:
        failures.append("mean_recall")
    for name, actual, limit in (
        ("mean_turns", summary.mean_turns, gate.maximum_mean_turns),
        ("mean_tokens", summary.mean_tokens, gate.maximum_mean_tokens),
        ("p95_latency_ms", summary.p95_latency_ms, gate.maximum_p95_latency_ms),
    ):
        if limit is not None and actual > limit:
            failures.append(name)
    return GateAssessment(tuple(failures))
