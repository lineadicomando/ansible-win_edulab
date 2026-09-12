import json
from pathlib import Path

from runlog import NotifyFn, RunResult, RunStatus, await_run, read_log, run_logged_async, start_logged

PROJECT_ROOT = Path(__file__).parent.parent


def build_playbook_command(
    playbook: str,
    l: str = "all",
    e: dict | None = None,
    inventory: str = "school",
) -> list[str]:
    cmd = ["ansible-playbook"]
    cmd += ["-i", str(PROJECT_ROOT / "inventories" / inventory / "hosts.yaml")]
    if l and l != "all":
        cmd += ["-l", l]
    cmd += [str(PROJECT_ROOT / "playbooks" / f"{playbook}.yaml")]
    if e:
        cmd += ["-e", json.dumps(e)]
    return cmd


async def run_raw(
    cmd: list[str],
    label: str = "run",
    notify: NotifyFn | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    redact: list[str] | None = None,
) -> RunResult:
    """Run an ansible command, streaming its output to a log file."""
    return await run_logged_async(cmd, PROJECT_ROOT, label, notify, timeout, env, redact)


async def run_command(
    cmd: list[str],
    label: str = "run",
    notify: NotifyFn | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """run_raw, rendered for a tool result: output, exit code, log path."""
    result = await run_raw(cmd, label, notify, timeout, env)
    output = result.output
    if result.returncode != 0:
        output += f"\n[exit code {result.returncode}]"
    return f"{output}\n[log] {result.log_path}"


def start_run(
    cmd: list[str],
    label: str = "run",
    env: dict[str, str] | None = None,
    redact: list[str] | None = None,
) -> Path:
    """Start an ansible command in the background; return its log path."""
    return start_logged(cmd, PROJECT_ROOT, label, env=env, redact=redact)


def run_status(run: str = "latest", since_line: int = 0, max_lines: int = 200) -> RunStatus:
    """Read a run's log, whether it is still going or already finished."""
    return read_log(PROJECT_ROOT, run, since_line, max_lines)


async def wait_run(
    run: str = "latest",
    timeout: float = 900.0,
    since_line: int = 0,
    max_lines: int = 200,
    notify: NotifyFn | None = None,
) -> RunStatus:
    """Block until a background run ends, then read its log."""
    return await await_run(PROJECT_ROOT, run, timeout, since_line, max_lines, notify)
