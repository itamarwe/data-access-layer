"""Controlled SQL outcomes with replayable agents and explicit cost accounting.

Replay validates the benchmark machinery, not a model's ability to solve a task.
An actual agent implements TaskAgent and records usage for every model call.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from dal.application import CatalogService, SearchOptions

from .catalog_adapter import Utf8TokenEstimate


@dataclass(frozen=True)
class SqlTask:
    id: str
    question: str
    expected_rows: tuple[tuple[object, ...], ...]
    max_turns: int = 4
    max_tokens: int = 8000
    split: str = "development"
    ordered: bool = False

    def __post_init__(self):
        if not self.id or not self.question or self.max_turns < 1 or self.max_tokens < 1:
            raise ValueError("task identity, question and positive budgets are required")
        if self.split not in {"development", "held_out"}:
            raise ValueError("task split must be development or held_out")


@dataclass(frozen=True)
class ModelTurn:
    """Provider usage for one complete model call, including repeated tool context."""

    input_tokens: int
    output_tokens: int

    def __post_init__(self):
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token usage cannot be negative")


@dataclass(frozen=True)
class AgentTask:
    """Task input without evaluation answers or database fixture internals."""

    id: str
    question: str
    max_turns: int
    max_tokens: int


@dataclass(frozen=True)
class AgentAnswer:
    sql: str
    turns: tuple[ModelTurn, ...]
    mode: str  # live or replay; reported, never inferred from success

    def __post_init__(self):
        if not self.turns or self.mode not in {"live", "replay"}:
            raise ValueError("answer requires model-call usage and live/replay mode")


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object]
    response: object
    input_token_estimate: int
    output_token_estimate: int
    elapsed_ms: float
    error: str | None = None


class ContextSession:
    """Records every discovery attempt, including failures, through shared services."""

    def __init__(self, catalog: CatalogService):
        self.catalog = catalog
        self.calls: list[ToolCall] = []

    def call(self, name: str, **arguments):
        started = time.perf_counter()
        response, error = None, None
        try:
            if name == "search":
                query = arguments["query"]
                options = SearchOptions(token_budget=int(arguments.get("token_budget", 1600)))
                response = asdict(self.catalog.search(query, kind=arguments.get("kind"), options=options))
            elif name == "get":
                value = self.catalog.get(arguments["kind"], arguments["object_id"])
                response = asdict(value) if value else None
            elif name in {"neighbors", "evidence"}:
                values = getattr(self.catalog, name)(arguments["object_id"])
                response = [asdict(value) for value in values]
            else:
                raise ValueError(f"unknown context tool: {name}")
            return response
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            counter = Utf8TokenEstimate()
            self.calls.append(ToolCall(
                name, arguments, response,
                counter.count(json.dumps(arguments, default=str)),
                counter.count(json.dumps(response if error is None else {"error": error}, default=str)),
                (time.perf_counter() - started) * 1000, error,
            ))


class TaskAgent(Protocol):
    def __call__(self, task: AgentTask, context: ContextSession) -> AgentAnswer: ...


@dataclass(frozen=True)
class SqlTaskResult:
    task_id: str
    correct: bool
    within_budget: bool
    mode: str
    turns: int
    input_tokens: int
    output_tokens: int
    elapsed_ms: float
    sql: str
    rows: tuple[tuple[object, ...], ...]
    calls: tuple[ToolCall, ...]
    error: str | None = None

    @property
    def success_at_budget(self):
        return self.correct and self.within_budget


def evaluate_sql_task(
    task: SqlTask, agent: TaskAgent, catalog: CatalogService, database: Path,
) -> SqlTaskResult:
    """Judge result values and multiplicity against a controlled read-only fixture.

Model tokens already include context consumed by the model. Tool estimates are
reported separately and are not added again. The database contains synthetic
fixtures only; no customer warehouse queries are executed by this runner.
"""
    started = time.perf_counter()
    session = ContextSession(catalog)
    answer = agent(AgentTask(task.id, task.question, task.max_turns, task.max_tokens), session)
    input_tokens = sum(turn.input_tokens for turn in answer.turns)
    output_tokens = sum(turn.output_tokens for turn in answer.turns)
    rows, error = (), None
    try:
        rows = _query(database, answer.sql)
        correct = rows == task.expected_rows if task.ordered else Counter(rows) == Counter(task.expected_rows)
    except (sqlite3.Error, ValueError) as exc:
        correct, error = False, f"{type(exc).__name__}: {exc}"
    return SqlTaskResult(
        task.id, correct,
        len(answer.turns) <= task.max_turns and input_tokens + output_tokens <= task.max_tokens,
        answer.mode, len(answer.turns), input_tokens, output_tokens,
        (time.perf_counter() - started) * 1000, answer.sql, rows, tuple(session.calls), error,
    )


def _query(database: Path, sql: str) -> tuple[tuple[object, ...], ...]:
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
               sqlite3.SQLITE_RECURSIVE}
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    remaining = 1000

    def progress():
        nonlocal remaining
        remaining -= 1
        return int(remaining <= 0)

    try:
        connection.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        connection.set_progress_handler(progress, 1000)
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise ValueError("task answer must return rows")
        rows = tuple(cursor.fetchmany(10_001))
        if len(rows) > 10_000:
            raise ValueError("task answer exceeds fixture result limit")
        return rows
    finally:
        connection.close()


@dataclass(frozen=True)
class SqlAblation:
    baseline: SqlTaskResult
    candidate: SqlTaskResult

    def __post_init__(self):
        if self.baseline.task_id != self.candidate.task_id or self.baseline.mode != self.candidate.mode:
            raise ValueError("ablation requires the same task and execution mode")

    @property
    def success_at_budget_delta(self) -> int:
        return int(self.candidate.success_at_budget) - int(self.baseline.success_at_budget)


def ablate_sql_task(task: SqlTask, agent: TaskAgent, baseline: CatalogService,
                   candidate: CatalogService, database: Path) -> SqlAblation:
    """Same agent, question, expected rows and budgets; only available context changes."""
    return SqlAblation(evaluate_sql_task(task, agent, baseline, database),
                       evaluate_sql_task(task, agent, candidate, database))
