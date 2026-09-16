"""Catalog query command registration and dispatch."""

from __future__ import annotations

import argparse
from pathlib import Path

from dal.application import BundleCatalog, CatalogService, RESOURCE_KINDS
from dal.application.models import DEFAULT_TOKEN_BUDGET, SearchOptions

from .contracts import CommandOutcome


def register(commands) -> None:
    connections = commands.add_parser("connections", help="Show business relations, data joins and semantic-to-data mappings; membership and references remain resource fields.")
    connections.add_argument("id")
    connections.add_argument("--limit", type=int, default=20)
    connections.set_defaults(handler=run_connections)
    search = commands.add_parser("search", help="Search all catalog resource types.")
    _search_arguments(search)
    search.add_argument("--kind", choices=RESOURCE_KINDS)
    search.set_defaults(handler=run_search)
    for kind in RESOURCE_KINDS:
        resource = commands.add_parser(
            kind.replace("_", "-"), help=f"Work with {kind} resources.",
        )
        actions = resource.add_subparsers(dest="action", required=True)
        listing = actions.add_parser("list", help=f"List {kind} resources.")
        listing.add_argument("--limit", type=int, default=20)
        listing.add_argument("--offset", type=int, default=0)
        listing.add_argument("--include-deprecated", action="store_true")
        if kind == "column":
            listing.add_argument("--table", help="Only columns belonging to this table ID.")
        listing.set_defaults(handler=run_resource)
        get = actions.add_parser("get", help=f"Get one {kind} resource.")
        get.add_argument("id")
        if kind == "table":
            get.add_argument("--columns-limit", type=int, default=20)
            get.add_argument("--columns-offset", type=int, default=0)
        get.set_defaults(handler=run_resource)
        for action in ("neighbors", "evidence"):
            context = actions.add_parser(action, help=f"Read {action} for one {kind}.")
            context.add_argument("id")
            context.add_argument("--limit", type=int, default=20)
            if action == "evidence":
                context.add_argument("--claim", help="Exact claim path, for example /description.")
                if kind == "table":
                    context.add_argument("--column", help="Evidence for one column ID belonging to this table.")
            context.set_defaults(handler=run_resource)
        typed_search = actions.add_parser("search", help=f"Search {kind} resources.")
        _search_arguments(typed_search)
        if kind == "column":
            typed_search.add_argument("--table", help="Search only columns belonging to this table ID.")
        typed_search.set_defaults(handler=run_resource)


def run_search(arguments: argparse.Namespace) -> CommandOutcome:
    result = _service(arguments).search(
        arguments.query, kind=arguments.kind, weights=_weights(arguments.weight),
        options=SearchOptions(token_budget=arguments.token_budget, include_deprecated=arguments.include_deprecated),
    )
    return CommandOutcome(result)


def run_connections(arguments):
    return CommandOutcome(_service(arguments).connections(arguments.id, limit=arguments.limit))


def run_resource(arguments: argparse.Namespace) -> CommandOutcome:
    service = _service(arguments)
    kind = arguments.command.replace("-", "_")
    if arguments.action == "list":
        results = service.list(kind, limit=arguments.limit, offset=arguments.offset, include_deprecated=arguments.include_deprecated,
                               parent_id=getattr(arguments, "table", None))
        return CommandOutcome({
            "kind": kind, "results": results,
            "limit": arguments.limit, "offset": arguments.offset,
        })
    if arguments.action == "get":
        result = (service.table_detail(arguments.id, limit=arguments.columns_limit, offset=arguments.columns_offset)
                  if kind == "table" else service.get(kind, arguments.id))
        if result is None:
            return CommandOutcome(
                {"error": "resource not found", "id": arguments.id, "kind": kind}, 1,
            )
        return CommandOutcome(result)
    if arguments.action in {"neighbors", "evidence"}:
        if service.get(kind, arguments.id) is None:
            return CommandOutcome({"object_id": arguments.id, arguments.action: []})
        values = (service.evidence(arguments.id, limit=arguments.limit,
                                   column_id=getattr(arguments, "column", None), claim_path=arguments.claim)
                  if arguments.action == "evidence" else service.neighbors(arguments.id, limit=arguments.limit))
        return CommandOutcome({"object_id": arguments.id, arguments.action: values})
    result = service.search_kind(
        kind, arguments.query, weights=_weights(arguments.weight),
        options=SearchOptions(token_budget=arguments.token_budget, include_deprecated=arguments.include_deprecated),
        parent_id=getattr(arguments, "table", None),
    )
    return CommandOutcome(result)


def _service(arguments: argparse.Namespace) -> CatalogService:
    bundle = Path(arguments.bundle) if arguments.bundle else Path(arguments.repository) / ".dal" / "query"
    return CatalogService(BundleCatalog(bundle))


def _search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query")
    parser.add_argument(
        "--weight", action="append", default=[], metavar="NAME=VALUE",
        help="Override lexical, embedding, graph, evidence, or publication weight.",
    )
    parser.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET, help="Maximum estimated output tokens (UTF-8 bytes / 4); default 3200, minimum 400 for explicitly compact lookups.")
    parser.add_argument("--include-deprecated", action="store_true")


def _weights(values: list[str]) -> dict[str, float]:
    result = {}
    for value in values:
        name, separator, raw = value.partition("=")
        if not separator or not name or not raw:
            raise ValueError(f"invalid weight override: {value}")
        try:
            result[name] = float(raw)
        except ValueError as error:
            raise ValueError(f"invalid weight override: {value}") from error
    return result
