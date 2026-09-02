import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, CallToolResult, ListToolsResult, PaginatedRequestParams, CallToolRequestParams

from ansible_runner import build_playbook_command, run_command
from inventory import list_inventories, load_inventory

app = Server("win-edulab")


def _get_tools() -> list[Tool]:
    """Generate list of available tools."""
    return [
        Tool(
            name="get_inventory",
            description=(
                "Returns hosts and groups from an inventory with their IP and MAC addresses. "
                "Call this before run_tasks or run_playbook to discover available host and group names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "inventory": {
                        "type": "string",
                        "description": (
                            f"Inventory name under inventories/. "
                            f"Available: {list_inventories()}"
                        ),
                        "default": "school",
                    }
                },
            },
        ),
        Tool(
            name="run_playbook",
            description=(
                "Run a standalone playbook from the playbooks/ directory. "
                "Use for specialised playbooks such as veyon, wol, seb_classroom, autologon."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "playbook": {
                        "type": "string",
                        "description": (
                            "Playbook name without the .yaml extension. "
                            "E.g. 'veyon', 'wol', 'seb_classroom', 'autologon'."
                        ),
                    },
                    "l": {
                        "type": "string",
                        "description": "Ansible limit: single hostname or group name.",
                        "default": "all",
                    },
                    "e": {
                        "type": "object",
                        "description": (
                            "Additional playbook-specific extra vars. "
                            "E.g. {\"target_hosts\": \"students\"}"
                        ),
                        "default": {},
                    },
                    "inventory": {
                        "type": "string",
                        "default": "school",
                    },
                },
                "required": ["playbook"],
            },
        ),
    ]


async def handle_list_tools(ctx: ServerRequestContext, params: PaginatedRequestParams) -> ListToolsResult:
    return ListToolsResult(tools=_get_tools())


async def handle_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    name = params.name
    arguments = params.arguments or {}

    if name == "get_inventory":
        inventory = arguments.get("inventory", "school")
        try:
            data = load_inventory(inventory)
        except FileNotFoundError as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error: {e}")])
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, indent=2))])

    if name == "run_playbook":
        playbook: str = arguments.get("playbook")
        if not playbook:
            return CallToolResult(content=[TextContent(type="text", text="Error: playbook is required")])
        l: str = arguments.get("l", "all")
        e: dict = arguments.get("e") or {}
        inventory: str = arguments.get("inventory", "school")

        cmd = build_playbook_command(playbook, l, e or None, inventory)
        output = await asyncio.to_thread(run_command, cmd)
        return CallToolResult(content=[TextContent(type="text", text=output)])

    return CallToolResult(content=[TextContent(type="text", text=f"Unknown tool: {name}")])


app.add_request_handler("tools/list", PaginatedRequestParams, handle_list_tools)
app.add_request_handler("tools/call", CallToolRequestParams, handle_call_tool)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def cli():
    asyncio.run(main())


if __name__ == "__main__":
    cli()
