"""The same DAL application services exposed to MCP clients."""

from pathlib import Path

from .contracts import CommandOutcome


def register(commands):
    command = commands.add_parser("mcp", help="Serve DAL tools over MCP stdio.")
    command.set_defaults(handler=run)


def run(arguments):
    from dal.api import ServerConfig
    from dal.api.services import APIServices
    from dal.mcp import create_mcp

    root = Path(arguments.repository)
    bundle = Path(arguments.bundle) if arguments.bundle else root / ".dal" / "query"
    services = APIServices.create(ServerConfig(root, bundle))
    create_mcp(services.catalog, services.health).run(transport="stdio")
    return CommandOutcome(None)
