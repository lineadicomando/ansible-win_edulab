"""Configuration checks run before a command, not after it has failed.

A missing vault or an unreadable SSH key surfaces at the far end of Ansible as
a connection error per host, which reads like a lab that is switched off. These
checks name the actual cause first, so a run is refused for a reason the caller
can act on.
"""
from __future__ import annotations

import configparser
import re
from pathlib import Path

import yaml

from inventory import list_inventories

PROJECT_ROOT = Path(__file__).parent.parent

_VAULT_HEADER = "$ANSIBLE_VAULT"


def preflight(inventory: str = "school") -> list[str]:
    """Return what is missing for this inventory; an empty list means ready."""
    root = PROJECT_ROOT / "inventories" / inventory
    if not root.is_dir():
        available = ", ".join(list_inventories())
        return [f"Inventory {inventory!r} not found. Available: {available}"]

    problems: list[str] = []

    hosts_file = root / "hosts.yaml"
    if not hosts_file.exists():
        problems.append(f"{_rel(hosts_file)} is missing: this inventory has no host list.")

    problems += _vault_problems(root)
    problems += _ssh_key_problems(root)
    return problems


def _vault_problems(root: Path) -> list[str]:
    problems: list[str] = []

    # A vault.yaml.example with no vault.yaml beside it is an inventory whose
    # secrets were never initialised.
    for example in root.rglob("vault.yaml.example"):
        if not example.with_suffix("").exists():
            problems.append(
                f"{_rel(example.with_suffix(''))} is missing while "
                f"{_rel(example)} exists: this inventory's vault was never "
                f"initialised (see the win-edulab-vault skill)."
            )

    if any(_is_vault(path) for path in root.rglob("*.yaml")):
        password_file = _vault_password_file()
        if password_file is None:
            problems.append(
                "This inventory holds vault-encrypted files but ansible.cfg "
                "sets no vault_password_file."
            )
        elif not password_file.exists():
            problems.append(
                f"Vault password file {_rel(password_file)} is missing, and "
                f"this inventory holds vault-encrypted files."
            )

    return problems


def _ssh_key_problems(root: Path) -> list[str]:
    problems: list[str] = []
    for vars_file in root.glob("group_vars/*/vars.yaml"):
        for key in _ssh_identities(vars_file):
            if not Path(key).expanduser().exists():
                problems.append(
                    f"SSH key {key} is referenced by {_rel(vars_file)} but does not exist."
                )
    return problems


def _ssh_identities(path: Path) -> list[str]:
    """The -i paths in a vars file's ansible_ssh_common_args, if any."""
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(data, dict):
        return []
    args = data.get("ansible_ssh_common_args")
    if not isinstance(args, str):
        return []
    args = _resolve(args, data)
    # A path still holding a reference comes from somewhere this check cannot
    # see (the vault, host_vars, the command line): leave it to Ansible.
    return [path for path in re.findall(r"-i\s+(\S+)", args) if "{{" not in path]


def _resolve(value: str, data: dict) -> str:
    """Substitute the plain {{ name }} references a vars file defines itself."""
    def replace(match: re.Match) -> str:
        other = data.get(match.group(1))
        return other if isinstance(other, str) else match.group(0)

    for _ in range(2):  # enough for a reference that points at a reference
        resolved = re.sub(r"\{\{\s*(\w+)\s*\}\}", replace, value)
        if resolved == value:
            break
        value = resolved
    return value


def _vault_password_file() -> Path | None:
    config = configparser.ConfigParser()
    try:
        config.read(PROJECT_ROOT / "ansible.cfg")
    except configparser.Error:
        return None
    value = config.get("defaults", "vault_password_file", fallback=None)
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _is_vault(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return handle.read(len(_VAULT_HEADER)) == _VAULT_HEADER
    except OSError:
        return False


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
