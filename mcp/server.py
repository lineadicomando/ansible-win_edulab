import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, CallToolResult, ListToolsResult, PaginatedRequestParams, CallToolRequestParams

from ansible_runner import build_playbook_command, run_command, run_status, start_run
from runlog import NotifyFn, format_status
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
                    "background": {
                        "type": "boolean",
                        "description": (
                            "If true, start the run and return its run id immediately "
                            "instead of waiting for it to finish, then follow it with "
                            "run_status. Use this for runs over a whole lab, which take "
                            "minutes, so their output can be reported as it arrives."
                        ),
                        "default": False,
                    },
                },
                "required": ["playbook"],
            },
        ),
        Tool(
            name="run_status",
            description=(
                "Read the log of a run started with background=true: the new output "
                "since a given line, and whether the run is still going. "
                "Poll this to follow a long playbook while it runs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run": {
                        "type": "string",
                        "description": (
                            "Run id, as returned by a background run. "
                            "'latest' (the default) is the most recent run."
                        ),
                        "default": "latest",
                    },
                    "since_line": {
                        "type": "integer",
                        "description": (
                            "Line to resume from: pass the since_line the previous "
                            "call reported, to get only what is new."
                        ),
                        "default": 0,
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Most lines to return in one call.",
                        "default": 200,
                    },
                },
            },
        ),
    ]


def _progress_notifier(ctx: ServerRequestContext) -> NotifyFn | None:
    """Relay a run's output as progress notifications, if the client wants them.

    Clients opt in per request by sending a progress token; without one there
    is nobody to notify and the run streams to its log file only.
    """
    token = (ctx.meta or {}).get("progress_token")
    if token is None:
        return None

    async def notify(progress: int, message: str) -> None:
        await ctx.session.send_progress_notification(
            progress_token=token,
            progress=progress,
            message=message,
            related_request_id=ctx.request_id,
        )

    return notify


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
        label = f"{playbook}-{l}"

        if arguments.get("background", False):
            path = start_run(cmd, label)
            return CallToolResult(content=[TextContent(
                type="text",
                text=(
                    f"Started run {path.name}\n"
                    f"[log] {path}\n\n"
                    f'Follow it with run_status(run="{path.name}", since_line=0).'
                ),
            )])

        output = await run_command(cmd, label, _progress_notifier(ctx))
        return CallToolResult(content=[TextContent(type="text", text=output)])

    if name == "run_status":
        try:
            status = run_status(
                arguments.get("run", "latest"),
                int(arguments.get("since_line", 0)),
                int(arguments.get("max_lines", 200)),
            )
        except FileNotFoundError as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error: {e}")])
        return CallToolResult(content=[TextContent(type="text", text=format_status(status))])

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
