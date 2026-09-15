"""Thin benchmark adapter over the production CatalogService."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from typing import Protocol

from dal.application import CatalogService, SearchOptions, SearchResponse

from .model import EvaluationCase, SearchObservation


class TokenCounter(Protocol):
    def count(self, text: str) -> int:
        ...


class Utf8TokenEstimate:
    """Deterministic local fallback; callers may inject their production tokenizer."""

    def count(self, text: str) -> int:
        return math.ceil(len(text.encode("utf-8")) / 4)


class CatalogSearchAdapter:
    def __init__(
        self, service: CatalogService, *,
        token_counter: TokenCounter | None = None,
        clock_ms: Callable[[], float] | None = None,
        weights: Mapping[str, float] | None = None,
        options: SearchOptions | None = None,
    ):
        self.service = service
        self.token_counter = token_counter or Utf8TokenEstimate()
        self.clock_ms = clock_ms or _clock_ms
        self.weights = weights
        self.options = options or SearchOptions()

    def __call__(self, case: EvaluationCase) -> SearchObservation:
        input_tokens = self.token_counter.count(case.question)
        output_budget = max(1, case.max_tokens - input_tokens)
        options = replace(self.options, token_budget=output_budget)
        started = self.clock_ms()
        response = self.service.search(
            case.question, weights=self.weights, options=options,
        )
        elapsed = self.clock_ms() - started
        identifiers = _response_ids(response)
        embeddings = response.capabilities.embedding == "available"
        return SearchObservation(
            returned_object_ids=identifiers,
            turns=1,
            input_tokens=input_tokens,
            output_tokens=self.token_counter.count(_response_text(response)),
            latency_ms=elapsed,
            embedding_available=embeddings,
            degradation_reason=(
                None if embeddings else response.capabilities.embedding_reason
            ),
        )


def _clock_ms() -> float:
    return time.perf_counter() * 1_000


def _response_text(response: object) -> str:
    return json.dumps(
        asdict(response), default=str, ensure_ascii=False,
        separators=(",", ":"), sort_keys=True,
    )


def _response_ids(response: SearchResponse) -> tuple[str, ...]:
    """Score retrieved objects, never incidental IDs in links or evidence."""
    values = [
        *(item.object.id for item in response.results),
        *(item.id for item in response.also_matched),
    ]
    if response.start_with:
        values.append(response.start_with.object_id)
    if response.relevant_doctrine:
        values.append(response.relevant_doctrine.id)
    if response.relevant_gold_query:
        values.append(response.relevant_gold_query.id)
    return tuple(dict.fromkeys(values))
