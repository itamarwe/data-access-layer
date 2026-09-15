"""Success-at-budget evaluation tests."""

from dal.evaluation import EvaluationCase, SearchObservation, evaluate


def test_success_at_budget_requires_correctness_and_efficiency():
    cases = (
        EvaluationCase("good", "orders", frozenset({"orders"}), 1, 100),
        EvaluationCase("expensive", "customers", frozenset({"customers"}), 1, 100),
        EvaluationCase("miss", "revenue", frozenset({"revenue"}), 1, 100),
    )
    observations = {
        "good": SearchObservation(("orders",), 1, 40, 20, 5.0),
        "expensive": SearchObservation(("customers",), 1, 90, 20, 8.0),
        "miss": SearchObservation(("other",), 1, 20, 20, 2.0),
    }

    run = evaluate("default", cases, lambda case: observations[case.case_id])

    assert run.summary.success_rate == 2 / 3
    assert run.summary.success_at_budget_rate == 1 / 3
    assert run.summary.mean_recall == 2 / 3
    assert run.summary.mean_input_tokens == 50
    assert run.summary.mean_output_tokens == 20
    assert run.summary.mean_tokens == 70
    assert run.summary.mean_turns == 1
    assert run.summary.mean_latency_ms == 5
    assert run.summary.p95_latency_ms == 8


def test_empty_evaluation_is_explicit():
    run = evaluate("empty", (), lambda _case: None)

    assert run.summary.cases == 0
    assert run.summary.success_at_budget_rate == 0.0


def test_latency_budget_is_accounted_separately_from_tokens_and_turns():
    case = EvaluationCase(
        "slow", "orders", frozenset({"orders"}), 1, 100,
        max_latency_ms=10,
    )

    run = evaluate(
        "slow", [case],
        lambda _: SearchObservation(("orders",), 1, 10, 10, 10.1),
    )

    assert run.results[0].success
    assert not run.results[0].within_budget
    assert not run.results[0].success_at_budget


def test_empty_expectation_requires_an_empty_result():
    case = EvaluationCase("absent", "unknown thing", frozenset(), 1, 100)

    empty = evaluate(
        "empty", [case], lambda _: SearchObservation((), 1, 1, 1, 1.0),
    )
    noisy = evaluate(
        "noisy", [case],
        lambda _: SearchObservation(("unrelated",), 1, 1, 1, 1.0),
    )

    assert empty.results[0].success_at_budget
    assert not noisy.results[0].success
