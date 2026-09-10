import json
from pathlib import Path

from runlog import run_logged

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


def run_command(cmd: list[str], label: str = "run") -> str:
    """Run an ansible-playbook command, streaming its output to a log file."""
    result = run_logged(cmd, PROJECT_ROOT, label)
    output = result.output
    if result.returncode != 0:
        output += f"\n[exit code {result.returncode}]"
    return f"{output}\n[log] {result.log_path}"
