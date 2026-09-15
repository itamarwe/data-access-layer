"""Optional local embedding providers; no synthetic semantic fallback."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol


class Embedder(Protocol):
    provider: str
    model_id: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> Iterable[Sequence[float]]:
        ...


class FastEmbedder:
    """Explicit fastembed adapter; construction may acquire its named model."""

    provider = "fastembed"

    def __init__(self, model_id: str = "BAAI/bge-small-en-v1.5", **options):
        from fastembed import TextEmbedding

        metadata = next(
            item for item in TextEmbedding.list_supported_models()
            if item["model"] == model_id
        )
        self.model_id = model_id
        self.dimensions = int(metadata["dim"])
        self._model = TextEmbedding(model_name=model_id, **options)

    def embed(self, texts: Sequence[str]) -> Iterable[Sequence[float]]:
        return self._model.embed(texts)


def embedding_health(embedder: Embedder | None) -> dict[str, object]:
    if embedder is None:
        return {
            "status": "unavailable",
            "reason": "local_embedder_not_configured",
        }
    return {
        "status": "available",
        "provider": embedder.provider,
        "model": embedder.model_id,
        "dimensions": embedder.dimensions,
    }
