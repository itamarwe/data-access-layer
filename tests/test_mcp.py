"""MCP uses the same service results and validation as other transports."""

import asyncio
from dataclasses import asdict

from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from dal.mcp import create_mcp


def test_mcp_tool_contract_and_shared_lookup(tmp_path):
    document = {"version": 1, "objects": [
        {"id": "table:orders", "kind": "table", "name": "orders", "grain": {"description": "one row per order"}},
    ]}
    catalog = CatalogService(BundleCatalog(BundleBuilder(tmp_path / "bundle").build(document).bundle))
    server = create_mcp(catalog, lambda: {"checked": ["files"]})

    async def inspect():
        registered = await server.list_tools()
        assert {tool.name for tool in registered} == {"search", "get", "connections", "neighbors", "evidence", "health"}
        assert all(tool.annotations.model_dump(by_alias=True)["readOnlyHint"] for tool in registered)
        result = await server.call_tool("get", {"kind": "table", "object_id": "table:orders"})
        return result

    result = asyncio.run(inspect())
    # SDK versions differ in the transport wrapper; content is always JSON text.
    import json
    blocks = result.content if hasattr(result, "content") else result[0] if isinstance(result, tuple) else result
    value = json.loads(blocks[0].text)
    assert value == {**asdict(catalog.get("table", "table:orders")), "columns": [],
                     "columns_page": {"limit": 20, "offset": 0, "has_more": False}, "next_commands": []}
