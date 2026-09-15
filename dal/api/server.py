"""Process entry point for the local DAL server."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app
from .config import ServerConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dal-server", description="Serve the DAL API and curator UI.")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--auth-token", default=os.environ.get("DAL_AUTH_TOKEN"))
    arguments = parser.parse_args(argv)
    try:
        config = ServerConfig(
            repository_root=arguments.repository,
            bundle=arguments.bundle,
            host=arguments.host,
            port=arguments.port,
            allow_remote=arguments.allow_remote,
            auth_token=arguments.auth_token,
        )
    except ValueError as error:
        parser.error(str(error))
    uvicorn.run(create_app(config), host=config.host, port=config.port)
    return 0
