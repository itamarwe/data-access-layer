"""MCP transport over the same catalog and health services as CLI and REST."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path

from dal.application import CatalogService, SearchOptions
from dal.application.models import DEFAULT_TOKEN_BUDGET


def _data(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return [_data(item) for item in value]
    if isinstance(value, dict):
        return {key: _data(item) for key, item in value.items()}
    return value


def create_mcp(catalog: CatalogService, health: Callable):
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:
        from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    server = FastMCP("dal", instructions=(
        "Break multi-part questions into distinct facts and search each fact separately. "
        "Use the returned context and next steps; retrieve more "
        "only where necessary. Evidence distinguishes physical, usage and curation. "
        "Publication is not proof: inspect claim values, measurement dates and "
        "contradictions before selecting a join. Empty results mean no match."
    ))
    annotations = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                  idempotentHint=True, openWorldHint=False)

    @server.tool(annotations=annotations)
    def search(query: str, kind: str | None = None, token_budget: int = DEFAULT_TOKEN_BUDGET,
               include_deprecated: bool = False, weights: dict[str, float] | None = None,
               parent_id: str | None = None):
        """Find relevant context within an estimated token budget; default excludes deprecated objects."""
        return _data(catalog.search(query, kind=kind, weights=weights, parent_id=parent_id, options=SearchOptions(
            token_budget=token_budget, include_deprecated=include_deprecated,
        )))

    @server.tool(annotations=annotations)
    def get(kind: str, object_id: str, columns_limit: int = 20, columns_offset: int = 0):
        """Read a known object in full, including actionable SQL and metadata."""
        return _data(catalog.table_detail(object_id, limit=columns_limit, offset=columns_offset)
                     if kind == "table" else catalog.get(kind, object_id))

    @server.tool(annotations=annotations)
    def connections(object_id: str, limit: int = 20):
        """Read business relations, data joins, and semantic-to-data mappings in separate groups."""
        return _data(catalog.connections(object_id, limit=limit))

    @server.tool(annotations=annotations)
    def neighbors(object_id: str, limit: int = 20):
        """Navigate resource fields, membership, definitions and references; not a relationship taxonomy."""
        return _data(catalog.neighbors(object_id, limit=limit))

    @server.tool(annotations=annotations)
    def evidence(object_id: str, limit: int = 20, column_id: str | None = None, claim_path: str | None = None):
        """Read supporting claim values, physical measurements and source dates."""
        return _data(catalog.evidence(object_id, limit=limit, column_id=column_id, claim_path=claim_path))

    @server.tool(name="health", annotations=annotations)
    def inspect_health():
        """Report checks performed, knowledge gaps and concrete recovery instructions."""
        return _data(health())

    return server


def main():
    from dal.api.config import ServerConfig
    from dal.api.services import APIServices

    parser = argparse.ArgumentParser(description="DAL context tools over MCP stdio")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    services = APIServices.create(ServerConfig(repository_root=args.repository, bundle=args.bundle))
    create_mcp(services.catalog, services.health).run(transport="stdio")


if __name__ == "__main__":
    main()
