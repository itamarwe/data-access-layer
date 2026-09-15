"""Single JSON-first command-line entry point for DAL."""

from __future__ import annotations

import argparse
import os
import sys

from dal.application import BundleNotFoundError
from dal.curation import CurationError
from dal.repository import RepositoryError

from . import (
    build_commands, health_commands, repository_commands, proposal_commands, mcp_commands, import_commands,
    query_commands, serve_commands,
)
from .contracts import CommandOutcome
from .serialization import dumps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dal", description="Query, validate, build, and curate DAL context.",
    )
    parser.add_argument(
        "--bundle", default=os.environ.get("DAL_BUNDLE"),
        help="Compiled query bundle path for search and typed resources.",
    )
    parser.add_argument("--repository", default=".", help="Directory containing semantic/*.yaml or *.json.")
    commands = parser.add_subparsers(dest="command", required=True)
    query_commands.register(commands)
    repository_commands.register(commands)
    build_commands.register(commands)
    health_commands.register(commands)
    proposal_commands.register(commands)
    serve_commands.register(commands)
    mcp_commands.register(commands)
    import_commands.register(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        outcome = arguments.handler(arguments)
    except (BundleNotFoundError, CurationError, RepositoryError, OSError, ValueError) as error:
        print(dumps({"error": str(error), "type": type(error).__name__}), file=sys.stderr)
        return 2
    if not isinstance(outcome, CommandOutcome):
        print(dumps({"error": "command returned an invalid outcome"}), file=sys.stderr)
        return 2
    if outcome.payload is None:
        return outcome.exit_code
    destination = sys.stderr if outcome.exit_code == 2 else sys.stdout
    print(dumps(outcome.payload), file=destination)
    return outcome.exit_code
