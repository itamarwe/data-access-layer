"""Stable identities for source objects that do not carry native IDs."""

from __future__ import annotations

import hashlib


def stable_id(kind: str, natural_key: str) -> str:
    """Return a deterministic opaque URN without leaking unsafe source names."""
    digest = hashlib.sha256(natural_key.encode("utf-8")).hexdigest()[:24]
    return f"urn:dal:{kind}:{digest}"
