import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, CallToolResult, ListToolsResult, PaginatedRequestParams, CallToolRequestParams

from adhoc import (
    CONFIRM_ABOVE,
    ENV as ADHOC_ENV,
    build_powershell_command,
    resolve_hosts,
    secret_values,
    summarise,
)
from ansible_runner import build_playbook_command, run_command, run_raw, run_status, start_run, wait_run
from runlog import NotifyFn, done_path, format_status
from inventory import list_inventories, load_inventory
from preflight import preflight

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
            name="run_powershell",
            description=(
                "Run a PowerShell script on lab hosts through ansible.windows.win_powershell, "
                "using the inventory's addresses, credentials and SSH settings. "
                "Use this for one-off queries and fixes; anything worth repeating belongs in a "
                "playbook or a win_workman role instead.\n"
                "The script's objects come back structured, not as console text: set "
                "$Ansible.Result to return exactly what you want, or just leave objects on the "
                "success stream. Other $Ansible members: Changed, Failed, Tmpdir, Diff.\n"
                "Notes that save a round trip:\n"
                "- The script runs in Windows PowerShell 5.1, not pwsh 7: no ternary operator, "
                "no ConvertFrom-Json -AsHashtable, no Get-Error.\n"
                "- Project objects with Select-Object before returning them; a bare Get-Process "
                "serialises megabytes and gets truncated.\n"
                "- Pass values through 'parameters' into a param() block rather than building "
                "them into the script text, and secrets through 'sensitive_parameters'; the "
                "script text itself is written to the run log.\n"
                "- Windows hosts only. The Linux DC is served by the samba-ad-dc MCP server."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": (
                            "The PowerShell script. Start it with a param() block when using "
                            "'parameters'."
                        ),
                    },
                    "l": {
                        "type": "string",
                        "description": (
                            "Ansible pattern: a hostname, a group, or a comma-separated list. "
                            "Required, and deliberately without a default: call get_inventory "
                            "if unsure what exists."
                        ),
                    },
                    "parameters": {
                        "type": "object",
                        "description": (
                            "Values for the script's param() block, passed typed rather than "
                            "interpolated. E.g. {\"Path\": \"C:\\\\temp\", \"Force\": true}"
                        ),
                        "default": {},
                    },
                    "sensitive_parameters": {
                        "type": "array",
                        "description": (
                            "Parameters passed as SecureString or PSCredential and kept out of "
                            "the logs. Each entry is {name, value} or {name, username, password}."
                        ),
                        "items": {"type": "object"},
                        "default": [],
                    },
                    "read_only": {
                        "type": "boolean",
                        "description": (
                            "True (the default) appends $Ansible.Changed = $false, so a query "
                            "does not report itself as a change. Set it to false for a script "
                            "that modifies the host."
                        ),
                        "default": True,
                    },
                    "depth": {
                        "type": "integer",
                        "description": (
                            "How deep returned objects are serialised. Raising it past 3 grows "
                            "the output fast; prefer Select-Object."
                        ),
                        "default": 3,
                    },
                    "error_action": {
                        "type": "string",
                        "enum": ["stop", "continue", "silently_continue"],
                        "description": (
                            "$ErrorActionPreference. 'stop' (the default) turns an error record "
                            "into a failed task instead of letting the script carry on."
                        ),
                        "default": "stop",
                    },
                    "chdir": {
                        "type": "string",
                        "description": "PowerShell location to set before running the script.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": (
                            f"Required to be true when the pattern selects more than "
                            f"{CONFIRM_ABOVE} hosts."
                        ),
                        "default": False,
                    },
                    "inventory": {
                        "type": "string",
                        "default": "school",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Seconds before the run is killed.",
                        "default": 300,
                    },
                    "background": {
                        "type": "boolean",
                        "description": (
                            "Start the run and return its id instead of waiting, then follow it "
                            "with run_status. The output is the raw one, not the summary."
                        ),
                        "default": False,
                    },
                },
                "required": ["script", "l"],
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
        Tool(
            name="wait_run",
            description=(
                "Wait for a run started with background=true and return its output "
                "once it ends. Prefer this over polling run_status in a loop: it "
                "comes back the moment the run finishes, so a long run cannot be "
                "started and then forgotten. If the wait runs out first, the result "
                "is still marked running and says where to resume — call again to "
                "keep waiting."
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
                    "timeout": {
                        "type": "integer",
                        "description": (
                            "Seconds to wait before returning with the run still "
                            "going. Clamped to 5..3600."
                        ),
                        "default": 900,
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


def _missing_config(inventory: str) -> str | None:
    """The tool result to return when the inventory is not ready, if it isn't."""
    problems = preflight(inventory)
    if not problems:
        return None
    return (
        f"Configuration missing for inventory {inventory!r}:\n"
        + "\n".join(f"- {problem}" for problem in problems)
        + "\n\nFix it before running, or say how you want to proceed. "
        "The ansible-vault-secrets, win-edulab-vault and win-edulab-inventory "
        "skills cover these."
    )


async def _run_powershell(ctx: ServerRequestContext, arguments: dict) -> CallToolResult:
    def fail(text: str) -> CallToolResult:
        return CallToolResult(content=[TextContent(type="text", text=text)])

    script: str = arguments.get("script") or ""
    l: str = arguments.get("l") or ""
    if not script.strip():
        return fail("Error: script is required")
    if not l.strip():
        return fail("Error: l is required: name the host or group to run on")

    inventory: str = arguments.get("inventory", "school")
    missing = _missing_config(inventory)
    if missing:
        return fail(missing)

    hosts = resolve_hosts(l, inventory)
    if not hosts:
        return fail(
            f"Pattern {l!r} matches no host in inventory {inventory!r}. "
            f"Call get_inventory to see the host and group names."
        )
    if len(hosts) > CONFIRM_ABOVE and not arguments.get("confirm", False):
        return fail(
            f"Pattern {l!r} selects {len(hosts)} hosts: "
            f"{', '.join(hosts)}.\n"
            f"Repeat the call with confirm=true if that is the intent."
        )

    sensitive = arguments.get("sensitive_parameters") or None
    cmd = build_powershell_command(
        script,
        l,
        inventory,
        parameters=arguments.get("parameters") or None,
        sensitive_parameters=sensitive,
        depth=int(arguments.get("depth", 3)),
        error_action=arguments.get("error_action", "stop"),
        read_only=arguments.get("read_only", True),
        chdir=arguments.get("chdir"),
    )
    label = f"ps-{l}"
    timeout = int(arguments.get("timeout", 300))
    redact = secret_values(sensitive)

    if arguments.get("background", False):
        path = start_run(cmd, label, env=ADHOC_ENV, redact=redact)
        return fail(
            f"Started run {path.name} on {len(hosts)} "
            f"host{'s' if len(hosts) != 1 else ''}\n"
            f"[log] {path}\n\n"
            f'Wait for it with wait_run(run="{path.name}"), which returns when it ends, '
            f'or read it as it goes with run_status(run="{path.name}", since_line=0).\n'
            f"[done] {done_path(path)} appears when the run ends: "
            f"a watcher outside this session can wait on that file."
        )

    result = await run_raw(cmd, label, _progress_notifier(ctx), timeout, ADHOC_ENV, redact)
    text = summarise(result.output)
    if result.timed_out:
        text += f"\n[timed out after {timeout}s]"
    elif result.returncode != 0 and not text:
        text += f"\n[exit code {result.returncode}]"
    return fail(f"{text}\n\n[log] {result.log_path}")


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
                    f'Wait for it with wait_run(run="{path.name}"), which returns when it ends, '
                    f'or read it as it goes with run_status(run="{path.name}", since_line=0).\n'
                    f"[done] {done_path(path)} appears when the run ends: "
                    f"a watcher outside this session can wait on that file."
                ),
            )])

        output = await run_command(cmd, label, _progress_notifier(ctx))
        return CallToolResult(content=[TextContent(type="text", text=output)])

    if name == "run_powershell":
        return await _run_powershell(ctx, arguments)

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

    if name == "wait_run":
        try:
            status = await wait_run(
                arguments.get("run", "latest"),
                max(5.0, min(3600.0, float(arguments.get("timeout", 900)))),
                int(arguments.get("since_line", 0)),
                int(arguments.get("max_lines", 200)),
                _progress_notifier(ctx),
            )
        except FileNotFoundError as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error: {e}")])
        # Still running means the wait expired, not that anything is wrong:
        # point back at wait_run so the caller can simply wait again.
        tool = "wait_run" if status.running else "run_status"
        return CallToolResult(content=[TextContent(type="text", text=format_status(status, tool))])

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
