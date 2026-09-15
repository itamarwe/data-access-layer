"""Controlled outcome tests use synthetic data and explicitly labelled replay agents."""

import sqlite3

import pytest

from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from dal.evaluation import CatalogSearchAdapter, EvaluationCase, evaluate
from dal.evaluation.sql_tasks import (
    AgentAnswer, ContextSession, ModelTurn, SqlTask, ablate_sql_task, evaluate_sql_task,
)


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE customers(id INTEGER, name TEXT);
            CREATE TABLE orders(id INTEGER, customer_id INTEGER, amount INTEGER, state TEXT);
            INSERT INTO customers VALUES (1, 'Ada'), (2, 'Ben');
            INSERT INTO orders VALUES (2, 1, 20, 'paid'), (1, 2, 10, 'paid'), (3, 1, 99, 'cancelled');
        """)
    return path


def catalog(tmp_path, *, doctrine=True):
    objects = [{"id": "table:orders", "kind": "table", "name": "orders"},
               {"id": "table:customers", "kind": "table", "name": "customers"}]
    if doctrine:
        objects.append({"id": "doctrine:revenue", "kind": "doctrine", "name": "Revenue methodology",
                        "content": "Revenue includes paid orders only; exclude cancelled orders."})
    return CatalogService(BundleCatalog(BundleBuilder(tmp_path).build({"version": 1, "objects": objects}).bundle))


def replay(sql, *, discover=True):
    def agent(task, context):
        if discover:
            context.call("search", query="orders customers", token_budget=1600)
            context.call("get", kind="table", object_id="table:orders")
        return AgentAnswer(sql, (ModelTurn(100, 20), ModelTurn(300, 40)), "replay")
    return agent


def test_wrong_join_fails_even_when_object_retrieval_passes(tmp_path, warehouse):
    service = catalog(tmp_path / "bundle")
    task = SqlTask("revenue-by-customer", "Paid revenue per customer", (("Ada", 20), ("Ben", 10)))
    retrieval = evaluate("objects", [EvaluationCase("objects", "orders customers",
                         frozenset({"table:orders", "table:customers"}), 1, 2000)], CatalogSearchAdapter(service))
    assert retrieval.results[0].success
    wrong = evaluate_sql_task(task, replay("SELECT c.name, SUM(o.amount) FROM orders o JOIN customers c ON o.id=c.id WHERE o.state='paid' GROUP BY c.name"), service, warehouse)
    right = evaluate_sql_task(task, replay("SELECT c.name, SUM(o.amount) FROM orders o JOIN customers c ON o.customer_id=c.id WHERE o.state='paid' GROUP BY c.name"), service, warehouse)
    assert not wrong.correct
    assert right.success_at_budget
    assert right.mode == "replay"
    assert (right.turns, right.input_tokens, right.output_tokens) == (2, 400, 60)
    assert len(right.calls) == 2
    assert all(call.output_token_estimate > 0 for call in right.calls)


def test_missing_filter_ablation_keeps_expected_outcome_fixed(tmp_path, warehouse):
    task = SqlTask("paid-revenue", "What is revenue?", ((30,),))

    def scripted_agent(task, context):
        method = context.call("get", kind="doctrine", object_id="doctrine:revenue")
        sql = "SELECT SUM(amount) FROM orders" + (" WHERE state='paid'" if method else "")
        return AgentAnswer(sql, (ModelTurn(100, 20),), "replay")

    comparison = ablate_sql_task(task, scripted_agent, catalog(tmp_path / "without", doctrine=False),
                                 catalog(tmp_path / "with"), warehouse)
    assert comparison.baseline.rows == ((129,),)
    assert comparison.candidate.rows == task.expected_rows
    assert comparison.success_at_budget_delta == 1


@pytest.mark.parametrize("sql", ["DELETE FROM orders", "ATTACH DATABASE ':memory:' AS other", "SELECT 1; SELECT 2"])
def test_answer_cannot_mutate_or_run_multiple_statements(tmp_path, warehouse, sql):
    service = catalog(tmp_path / "bundle")
    result = evaluate_sql_task(SqlTask("invalid", "Answer", ((1,),)), replay(sql, discover=False), service, warehouse)
    assert not result.correct
    assert result.error
    with sqlite3.connect(warehouse) as db:
        assert db.execute("SELECT COUNT(*) FROM orders").fetchone() == (3,)


def test_budget_and_failed_discovery_are_recorded(tmp_path, warehouse):
    service = catalog(tmp_path / "bundle")
    session = ContextSession(service)
    with pytest.raises(ValueError):
        session.call("missing_tool", query="orders")
    assert session.calls[0].error
    result = evaluate_sql_task(SqlTask("budget", "Answer", ((1,),), max_turns=1, max_tokens=100),
                               replay("SELECT 1", discover=False), service, warehouse)
    assert result.correct
    assert not result.success_at_budget


def test_row_multiplicity_is_part_of_correctness(tmp_path, warehouse):
    result = evaluate_sql_task(SqlTask("duplicates", "Answer", ((1,),)),
                               replay("SELECT 1 UNION ALL SELECT 1", discover=False),
                               catalog(tmp_path / "bundle"), warehouse)
    assert not result.correct


def test_agent_cannot_read_expected_answers_from_task_input(tmp_path, warehouse):
    def agent(task, context):
        assert not hasattr(task, "expected_rows")
        assert set(vars(task)) == {"id", "question", "max_turns", "max_tokens"}
        return AgentAnswer("SELECT 1", (ModelTurn(10, 2),), "replay")

    result = evaluate_sql_task(SqlTask("hidden", "Return one", ((1,),), split="held_out"),
                               agent, catalog(tmp_path / "bundle"), warehouse)
    assert result.correct
