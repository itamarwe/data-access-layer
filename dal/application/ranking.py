"""Pure ranking functions for catalog retrieval."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

from .models import CatalogObject, RankingSignals, RankingWeights


def tokenize(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        token for token in re.findall(r"[a-z0-9_]+", value.lower()) if len(token) > 1
    ))


def cosine(query: Sequence[float], candidate: Sequence[float]) -> float:
    if len(query) != len(candidate) or not query:
        return 0.0
    query_norm = math.sqrt(sum(value * value for value in query))
    candidate_norm = math.sqrt(sum(value * value for value in candidate))
    if query_norm == 0 or candidate_norm == 0:
        return 0.0
    return max(0.0, sum(left * right for left, right in zip(query, candidate)) /
               (query_norm * candidate_norm))


def normalized(values: Mapping[str, float]) -> dict[str, float]:
    maximum = max(values.values(), default=0.0)
    return {key: value / maximum if maximum else 0.0 for key, value in values.items()}


def publication_signal(item: CatalogObject) -> float:
    status = publication_status(item)
    return {"published": 1.0, "deprecated": 0.0}.get(status, 0.5)


def publication_status(item: CatalogObject) -> str | None:
    return str(item.payload.get("status", "published"))


def combine(signals: RankingSignals, weights: RankingWeights) -> float:
    return sum(
        getattr(signals, name) * weight for name, weight in weights.as_dict().items()
    )
