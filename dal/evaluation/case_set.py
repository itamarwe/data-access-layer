"""Strict loading for versioned benchmark cases, separate from gold queries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .gate import QualityGate
from .model import EvaluationCase

CASE_SET_FORMAT = "dal.benchmark-cases.v1"


@dataclass(frozen=True)
class BenchmarkCaseSet:
    name: str
    source: Mapping[str, object]
    cases: tuple[EvaluationCase, ...]
    gate: QualityGate

    @property
    def evaluable_cases(self) -> tuple[EvaluationCase, ...]:
        return tuple(case for case in self.cases if case.evaluable)

    @property
    def blocked_cases(self) -> tuple[EvaluationCase, ...]:
        return tuple(case for case in self.cases if not case.evaluable)


def load_case_set(path: Path | str) -> BenchmarkCaseSet:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or value.get("format") != CASE_SET_FORMAT:
        raise ValueError("unsupported benchmark case-set format")
    name = value.get("name")
    source = value.get("source")
    raw_cases = value.get("cases")
    gate = value.get("gate", {})
    if (
        not isinstance(name, str) or not isinstance(source, Mapping)
        or not isinstance(raw_cases, list) or not isinstance(gate, Mapping)
    ):
        raise ValueError("benchmark case-set fields are invalid")
    cases = tuple(_case(item) for item in raw_cases)
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("benchmark case IDs must be unique")
    try:
        configured_gate = QualityGate(**gate)
    except TypeError as error:
        raise ValueError("benchmark quality gate is invalid") from error
    return BenchmarkCaseSet(name, source, cases, configured_gate)


def _case(value: object) -> EvaluationCase:
    if not isinstance(value, Mapping):
        raise ValueError("benchmark case must be an object")
    allowed = {
        "case_id", "question", "expected_object_ids", "max_turns", "max_tokens",
        "category", "source_refs", "evaluable", "not_evaluable_reason",
        "max_latency_ms",
    }
    if set(value) - allowed:
        raise ValueError("benchmark case has unknown fields")
    if not isinstance(value.get("question"), str) or not value["question"]:
        raise ValueError("benchmark case question must be a non-empty string")
    expected = value.get("expected_object_ids")
    references = value.get("source_refs", [])
    if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
        raise ValueError("expected_object_ids must be an array of strings")
    if not isinstance(references, list) or not all(isinstance(item, str) for item in references):
        raise ValueError("source_refs must be an array of strings")
    return EvaluationCase(
        case_id=str(value.get("case_id", "")),
        question=str(value.get("question", "")),
        expected_object_ids=frozenset(expected),
        max_turns=int(value.get("max_turns", 0)),
        max_tokens=int(value.get("max_tokens", 0)),
        category=str(value.get("category", "retrieval")),
        source_refs=tuple(references),
        evaluable=value.get("evaluable", True) is True,
        not_evaluable_reason=value.get("not_evaluable_reason"),
        max_latency_ms=value.get("max_latency_ms"),
    )
