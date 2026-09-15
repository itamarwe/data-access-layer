"""Lazy local query embedding from compiler health metadata."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol
from functools import lru_cache


class QueryEmbedder(Protocol):
    dimensions: int

    def embed(self, texts: Sequence[str]) -> Iterable[Sequence[float]]:
        ...


class FastEmbedQueryEmbedder:
    def __init__(self, model: str, dimensions: int):
        from fastembed import TextEmbedding

        self.dimensions = dimensions
        self._model = TextEmbedding(model_name=model)

    def embed(self, texts: Sequence[str]) -> Iterable[Sequence[float]]:
        return self._model.embed(texts)


@lru_cache(maxsize=2)
def _cached_embedder(model: str, dimensions: int) -> FastEmbedQueryEmbedder:
    return FastEmbedQueryEmbedder(model, dimensions)


def local_embedder(
    health: Mapping[str, object],
) -> tuple[QueryEmbedder | None, str | None]:
    if health.get("status") != "available":
        return None, str(health.get("reason", "embedding_index_unavailable"))
    if health.get("provider") != "fastembed":
        return None, "embedding_provider_not_supported"
    model = health.get("model")
    dimensions = health.get("dimensions")
    if not isinstance(model, str) or not isinstance(dimensions, int):
        return None, "embedding_configuration_invalid"
    try:
        return _cached_embedder(model, dimensions), None
    except ImportError:
        return None, "local_embedding_dependency_missing"
    except (OSError, RuntimeError, ValueError):
        return None, "local_embedding_model_unavailable"
