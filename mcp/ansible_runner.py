import json
from pathlib import Path

from runlog import NotifyFn, RunResult, RunStatus, await_run, read_log, run_logged_async, secret_strings, start_logged

PROJECT_ROOT = Path(__file__).parent.parent

# Each fork is a Python process on the controller holding a connection open.
MAX_FORKS = 100


def validate_forks(forks) -> str | None:
    """Return an error message if forks is not a usable -f value, else None."""
    if forks is None:
        return None
    if isinstance(forks, bool) or not isinstance(forks, int):
        return "forks must be an integer"
    if not 1 <= forks <= MAX_FORKS:
        return f"forks must be between 1 and {MAX_FORKS}"
    return None


def validate_sensitive_vars(sensitive_vars) -> str | None:
    """Return an error message if sensitive_vars is not usable, else None."""
    if sensitive_vars is None:
        return None
    if not isinstance(sensitive_vars, dict) or not all(isinstance(k, str) for k in sensitive_vars):
        return "sensitive_vars must be an object of variable names to values"
    return None


def merge_sensitive_vars(e: dict | None, sensitive_vars: dict | None) -> tuple[dict | None, list[str]]:
    """Extra vars with the sensitive ones folded in, and the values to mask."""
    if not sensitive_vars:
        return e, []
    return {**(e or {}), **sensitive_vars}, secret_strings(sensitive_vars)


def build_playbook_command(
    playbook: str,
    l: str = "all",
    e: dict | None = None,
    inventory: str = "school",
    forks: int | None = None,
) -> list[str]:
    cmd = ["ansible-playbook"]
    cmd += ["-i", str(PROJECT_ROOT / "inventories" / inventory / "hosts.yaml")]
    if l and l != "all":
        cmd += ["-l", l]
    if forks is not None:
        cmd += ["-f", str(forks)]
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
    redact: list[str] | None = None,
) -> str:
    """run_raw, rendered for a tool result: output, exit code, log path."""
    result = await run_raw(cmd, label, notify, timeout, env, redact)
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
