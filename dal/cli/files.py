"""Read-only CLI file decoding."""

from __future__ import annotations

from pathlib import Path

from dal.documents import load_document


def read_document(path: str) -> dict[str, object]:
    source = Path(path)
    suffix = source.suffix.lower()
    document_format = "json" if suffix == ".json" else "yaml" if suffix in {".yaml", ".yml"} else None
    return load_document(source.read_text(encoding="utf-8"), document_format)
