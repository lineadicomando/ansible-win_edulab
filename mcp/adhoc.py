"""One-off PowerShell on lab hosts, through the project's Ansible inventory.

Everything a connection needs — address, credentials from the vault, SSH
arguments, powershell shell type — already lives in the inventory, so an ad-hoc
run of ansible.windows.win_powershell inherits it rather than restating it.

The module returns structured data: `result` when the script sets
$Ansible.Result, `output` as the serialised objects of the success stream, and
error records with their exception details. `summarise` folds that back into
something a reader can take in at a glance, collapsing the hosts of a lab that
all answered the same thing into one entry.
"""
from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path

from inventory import load_inventory

PROJECT_ROOT = Path(__file__).parent.parent

MODULE = "ansible.windows.win_powershell"

# Beyond this many hosts a command has to be asked for twice. A restart is
# routine on one PC and an event on a whole lab.
CONFIRM_ABOVE = 3

# Serialised PowerShell objects are open-ended in size: a Get-Process with no
# projection is megabytes. Cut it, and say so, rather than filling the context.
MAX_HOST_CHARS = 4000
MAX_TOTAL_CHARS = 24000

# Ad-hoc uses the minimal callback unless custom callbacks are turned on; this
# keeps the output parseable whatever the environment says.
ENV = {"ANSIBLE_LOAD_CALLBACK_PLUGINS": "0"}


def build_powershell_command(
    script: str,
    l: str,
    inventory: str = "school",
    *,
    parameters: dict | None = None,
    sensitive_parameters: list | None = None,
    depth: int = 3,
    error_action: str = "stop",
    read_only: bool = True,
    chdir: str | None = None,
) -> list[str]:
    """An `ansible -m win_powershell` command line for one script."""
    if read_only:
        # The module reports changed=true unless the script says otherwise, so
        # a plain query would read as a modification on every host.
        script = f"{script.rstrip()}\n$Ansible.Changed = $false\n"

    args: dict = {
        "script": _protect_templating(script),
        "depth": depth,
        "error_action": error_action,
    }
    if parameters:
        args["parameters"] = parameters
    if sensitive_parameters:
        args["sensitive_parameters"] = sensitive_parameters
    if chdir:
        args["chdir"] = chdir

    return [
        "ansible",
        "-i", str(PROJECT_ROOT / "inventories" / inventory / "hosts.yaml"),
        l,
        "-m", MODULE,
        # JSON module args: the script survives quotes, $ and newlines intact.
        "-a", json.dumps(args),
    ]


def _protect_templating(script: str) -> str:
    """Keep Jinja out of a script that happens to contain its delimiters.

    Module arguments are templated before they reach the host, so a literal
    {{ or {% in PowerShell would be eaten on the way.
    """
    if "{{" in script or "{%" in script:
        return "{% raw %}" + script + "{% endraw %}"
    return script


def secret_values(sensitive_parameters: list | None) -> list[str]:
    """The values a call must keep out of its log.

    Ansible marks sensitive_parameters no_log, which covers its own output but
    not the command line the runner records.
    """
    secrets: list[str] = []
    for entry in sensitive_parameters or []:
        if not isinstance(entry, dict):
            continue
        for key in ("value", "password"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                secrets.append(value)
    return secrets


def resolve_hosts(l: str, inventory: str = "school") -> list[str]:
    """The hosts an Ansible pattern selects, as far as the inventory shows.

    Used to size a command before running it, not to run it: exclusions are
    ignored, so the count errs on the high side, which is the safe way to be
    wrong about how many machines are about to be touched.
    """
    data = load_inventory(inventory)
    hosts, groups = data["hosts"], data["groups"]

    selected: set[str] = set()
    for token in (part.strip() for part in re.split(r"[,:]", l)):
        if not token or token[0] in "!&":
            continue
        if token in ("all", "*"):
            selected.update(hosts)
        elif token in groups:
            selected.update(groups[token])
        elif token in hosts:
            selected.add(token)
        else:
            selected.update(host for host in hosts if fnmatch(host, token))
            for group, members in groups.items():
                if fnmatch(group, token):
                    selected.update(members)
    return sorted(selected)


# "PC01 | SUCCESS => {" opens a result; the minimal callback dumps it as JSON
# indented by four, so the closing brace is the next line in column zero.
_OPEN_RE = re.compile(r"^(?P<host>\S+) \| (?P<status>[A-Z_]+!?) => \{\s*$")
_SKIPPED_RE = re.compile(r"^(?P<host>\S+) \| (?P<status>SKIPPED)\s*$")


def parse_results(text: str) -> tuple[list[tuple[str, str, dict]], list[str]]:
    """Split ad-hoc output into per-host results and whatever else it printed."""
    results: list[tuple[str, str, dict]] = []
    other: list[str] = []

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]

        skipped = _SKIPPED_RE.match(line)
        if skipped:
            results.append((skipped.group("host"), "SKIPPED", {}))
            index += 1
            continue

        opened = _OPEN_RE.match(line)
        if not opened:
            other.append(line)
            index += 1
            continue

        block = ["{"]
        index += 1
        while index < len(lines):
            block.append(lines[index])
            done = lines[index] == "}"
            index += 1
            if done:
                break
        try:
            data = json.loads("\n".join(block))
        except json.JSONDecodeError:
            other.extend(block)
            continue
        results.append((opened.group("host"), opened.group("status"), data))

    return results, other


def summarise(text: str) -> str:
    """Render ad-hoc output compactly, folding hosts that answered alike."""
    results, other = parse_results(text)
    if not results:
        return _truncate(text.strip(), MAX_TOTAL_CHARS)

    # Hosts keyed by what they said: a lab where every PC answers the same is
    # one entry, not twenty-five copies of it.
    folded: dict[tuple[str, str], list[str]] = {}
    for host, status, data in results:
        folded.setdefault((status, _render(status, data)), []).append(host)

    blocks = []
    # On a single host the tally would only repeat the line below it.
    if len(results) > 1:
        counts: dict[str, int] = {}
        for _, status, _ in results:
            counts[status] = counts.get(status, 0) + 1
        blocks.append(
            f"{len(results)} hosts: "
            + ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
        )

    for (status, body), hosts in folded.items():
        title = f"{_hosts_label(hosts)} | {status}"
        blocks.append(f"{title}\n{body}" if body else title)

    # ansible-core repeats each failure as an [ERROR] line as well; keep only
    # what the per-host blocks do not already say.
    rendered = "\n".join(blocks)
    leftover = [
        line for line in other
        if line.strip() and not _is_noise(line)
        and line.removeprefix("[ERROR]: ").strip() not in rendered
    ]
    if leftover:
        blocks.append("\n".join(leftover[:10]))

    return _truncate("\n\n".join(blocks), MAX_TOTAL_CHARS)


# What ansible-core prints around a failure besides the failure itself: the
# task dump and its origin, which repeat the script back at the reader.
_NOISE_RE = re.compile(r"^(Origin: <adhoc |\{'action': |\s*$)")


def _is_noise(line: str) -> bool:
    return bool(_NOISE_RE.match(line))


def _hosts_label(hosts: list[str]) -> str:
    if len(hosts) <= 6:
        return ", ".join(hosts)
    return f"{', '.join(hosts[:6])} and {len(hosts) - 6} more"


def _render(status: str, data: dict) -> str:
    """The part of a win_powershell result worth reading."""
    parts: list[str] = []

    if status not in ("SUCCESS", "CHANGED", "SKIPPED"):
        message = data.get("msg") or data.get("module_stderr") or ""
        if message:
            parts.append(str(message).strip())

    # The script's own answer when it set $Ansible.Result, the success stream
    # otherwise: showing both would mostly repeat the same values.
    if data.get("result"):
        parts.append(_dump(data["result"]))
    elif data.get("output"):
        parts.append(_dump(data["output"]))

    for key, label in (("host_out", ""), ("host_err", "host stderr")):
        value = (data.get(key) or "").strip()
        if value:
            parts.append(f"{label}: {value}" if label else value)

    for record in data.get("error") or []:
        detail = (record.get("output") or "").strip()
        if detail:
            parts.append(detail)

    for warning in data.get("warning") or []:
        parts.append(f"warning: {warning}")

    body = "\n".join(part for part in parts if part)
    if not body and status in ("SUCCESS", "CHANGED"):
        # A script that returned nothing and a rendering that dropped something
        # would otherwise look the same.
        body = "(no output)"
    return _truncate(body, MAX_HOST_CHARS)


def _dump(value) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = len(text) - limit
    return f"{text[:limit]}\n[... {cut} more characters; project the objects with Select-Object]"
