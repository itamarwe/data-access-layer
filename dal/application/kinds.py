"""Catalog resource kinds exposed by application adapters."""

RESOURCE_KINDS = (
    "database",
    "table",
    "column",
    "join",
    "metric",
    "entity",
    "property",
    "relation",
    "doctrine",
    "gold_query",
)


def require_kind(kind: str) -> str:
    if kind not in RESOURCE_KINDS:
        raise ValueError(f"unsupported resource kind: {kind}")
    return kind


def command_name(kind: str) -> str:
    return kind.replace("_", "-")
