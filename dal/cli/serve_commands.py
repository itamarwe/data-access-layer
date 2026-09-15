"""Lazy adapter for the optional local API server."""

from __future__ import annotations

import argparse
from pathlib import Path

from .contracts import CommandOutcome


def register(commands) -> None:
    serve = commands.add_parser("serve", help="Serve the DAL API and curator UI.")
    serve.add_argument("--repository", type=Path, default=argparse.SUPPRESS)
    serve.add_argument("--bundle", dest="server_bundle", type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--allow-remote", action="store_true")
    serve.add_argument("--auth-token")
    serve.set_defaults(handler=run)


def run(arguments: argparse.Namespace) -> CommandOutcome:
    argv = [
        "--repository", str(arguments.repository),
        "--bundle", str(arguments.server_bundle or arguments.bundle or Path(arguments.repository) / ".dal" / "query"),
        "--host", arguments.host,
        "--port", str(arguments.port),
    ]
    if arguments.allow_remote:
        argv.append("--allow-remote")
    if arguments.auth_token:
        argv.extend(("--auth-token", arguments.auth_token))
    code = _server_main(argv)
    return CommandOutcome({"status": "stopped"}, code)


def _server_main(argv: list[str]) -> int:
    from dal.api.server import main

    return main(argv)
