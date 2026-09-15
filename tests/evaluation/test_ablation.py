"""Paired ablation decision tests."""

import pytest

from dal.evaluation import (
    EvaluationCase, SearchObservation, compare_variants, evaluate,
)


def test_candidate_must_improve_budgeted_success_without_regression():
    cases = (
        EvaluationCase("one", "one", frozenset({"one"}), 1, 100),
        EvaluationCase("two", "two", frozenset({"two"}), 1, 100),
    )
    baseline = evaluate("without", cases, lambda case: _observation(case, case.case_id == "one"))
    candidate = evaluate("with", cases, lambda case: _observation(case, True))

    comparison = compare_variants(baseline, candidate)

    assert comparison.success_at_budget_delta == 0.5
    assert comparison.improved_cases == ("two",)
    assert comparison.regressed_cases == ()
    assert comparison.mean_turn_delta == 0
    assert comparison.mean_latency_ms_delta == 0
    assert comparison.adds_value


def test_incomparable_case_sets_are_rejected():
    first = evaluate("one", [EvaluationCase("one", "", frozenset(), 1, 1)], _empty)
    second = evaluate("two", [EvaluationCase("two", "", frozenset(), 1, 1)], _empty)

    with pytest.raises(ValueError, match="same case IDs"):
        compare_variants(first, second)


def test_equal_success_with_lower_paired_cost_adds_value():
    case = EvaluationCase("one", "one", frozenset({"one"}), 2, 100)
    baseline = evaluate(
        "baseline", [case],
        lambda _: SearchObservation(("one",), 2, 30, 30, 10.0),
    )
    candidate = evaluate(
        "candidate", [case],
        lambda _: SearchObservation(("one",), 1, 10, 20, 4.0),
    )

    comparison = compare_variants(baseline, candidate)

    assert comparison.success_at_budget_delta == 0
    assert comparison.mean_turn_delta == -1
    assert comparison.mean_token_delta == -30
    assert comparison.mean_latency_ms_delta == -6
    assert comparison.adds_value


def test_cost_tradeoff_does_not_claim_an_unambiguous_improvement():
    case = EvaluationCase("one", "one", frozenset({"one"}), 2, 100)
    baseline = evaluate(
        "baseline", [case],
        lambda _: SearchObservation(("one",), 1, 30, 30, 10.0),
    )
    candidate = evaluate(
        "candidate", [case],
        lambda _: SearchObservation(("one",), 2, 10, 20, 20.0),
    )

    assert not compare_variants(baseline, candidate).adds_value


def _observation(case: EvaluationCase, success: bool) -> SearchObservation:
    returned = (case.case_id,) if success else ()
    return SearchObservation(returned, 1, 20, 20, 1.0)


def _empty(_case: EvaluationCase) -> SearchObservation:
    return SearchObservation((), 1, 0, 0, 0.0)
