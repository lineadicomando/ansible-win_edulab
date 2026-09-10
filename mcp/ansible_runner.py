import json
from pathlib import Path

from runlog import NotifyFn, RunStatus, read_log, run_logged_async, start_logged

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


async def run_command(
    cmd: list[str],
    label: str = "run",
    notify: NotifyFn | None = None,
) -> str:
    """Run an ansible-playbook command, streaming its output to a log file."""
    result = await run_logged_async(cmd, PROJECT_ROOT, label, notify)
    output = result.output
    if result.returncode != 0:
        output += f"\n[exit code {result.returncode}]"
    return f"{output}\n[log] {result.log_path}"


def start_run(cmd: list[str], label: str = "run") -> Path:
    """Start an ansible-playbook command in the background; return its log path."""
    return start_logged(cmd, PROJECT_ROOT, label)


def run_status(run: str = "latest", since_line: int = 0, max_lines: int = 200) -> RunStatus:
    """Read a run's log, whether it is still going or already finished."""
    return read_log(PROJECT_ROOT, run, since_line, max_lines)
