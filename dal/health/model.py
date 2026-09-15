"""Stable health-check results with failures distinct from knowledge gaps."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthIssue:
    code: str
    location: str
    message: str
    recovery_command: str

    def __post_init__(self) -> None:
        if not self.recovery_command.strip():
            raise ValueError("every health issue requires a recovery command")


@dataclass(frozen=True)
class HealthResult:
    failures: tuple[HealthIssue, ...]
    gaps: tuple[HealthIssue, ...]
    checks: tuple[dict[str, object], ...] = ()

    @property
    def healthy(self) -> bool:
        return not self.failures


def health_result(
    failures: list[HealthIssue], gaps: list[HealthIssue], checks=(),
) -> HealthResult:
    key = lambda issue: (issue.location, issue.code, issue.message)
    return HealthResult(tuple(sorted(failures, key=key)), tuple(sorted(gaps, key=key)), tuple(checks))
