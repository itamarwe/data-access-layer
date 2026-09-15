from dal.evaluation import (
    EvaluationCase, QualityGate, SearchObservation, assess_gate, evaluate,
)


def test_gate_reports_each_failed_configured_threshold():
    case = EvaluationCase("miss", "question", frozenset({"expected"}), 1, 10)
    run = evaluate(
        "candidate", [case],
        lambda _: SearchObservation(("other",), 2, 6, 6, 20.0),
    )
    gate = QualityGate(
        minimum_success_at_budget_rate=1.0,
        minimum_mean_recall=1.0,
        maximum_mean_turns=1,
        maximum_mean_tokens=10,
        maximum_p95_latency_ms=10,
    )

    assessment = assess_gate(run, gate)

    assert assessment.failures == (
        "success_at_budget_rate", "mean_recall", "mean_turns", "mean_tokens",
        "p95_latency_ms",
    )
    assert not assessment.meets_gate


def test_gate_accepts_a_run_at_its_boundaries():
    case = EvaluationCase("hit", "question", frozenset({"expected"}), 1, 10)
    run = evaluate(
        "candidate", [case],
        lambda _: SearchObservation(("expected",), 1, 5, 5, 10.0),
    )

    assert assess_gate(
        run, QualityGate(maximum_mean_turns=1, maximum_mean_tokens=10,
                         maximum_p95_latency_ms=10),
    ).meets_gate
