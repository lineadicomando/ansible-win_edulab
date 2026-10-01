from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).parent.parent


def load_inventory(inventory: str = "school") -> dict:
    path = PROJECT_ROOT / "inventories" / inventory / "hosts.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Inventory not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return _parse(raw)


def list_inventories() -> list[str]:
    return sorted(p.name for p in (PROJECT_ROOT / "inventories").iterdir() if p.is_dir())


def _parse(raw: dict) -> dict:
    hosts: dict = {}
    direct: dict = {}
    children: dict = {}
    _walk(raw.get("all", {}), hosts, direct, children)
    groups = {name: _members(name, direct, children) for name in direct}
    return {"hosts": hosts, "groups": groups}


def _walk(node: dict, hosts: dict, direct: dict, children: dict, group_name: str = None):
    if group_name:
        direct.setdefault(group_name, [])
        children.setdefault(group_name, [])

    for host, vars_ in (node.get("hosts") or {}).items():
        if host not in hosts:
            hosts[host] = vars_ or {}
        if group_name and host not in direct[group_name]:
            direct[group_name].append(host)

    for child_name, child_node in (node.get("children") or {}).items():
        if group_name and child_name not in children[group_name]:
            children[group_name].append(child_name)
        _walk(child_node or {}, hosts, direct, children, child_name)


def _members(name: str, direct: dict, children: dict, seen: set = None) -> list[str]:
    """A group's hosts, its own first and then those of its child groups.

    A group may be made of children alone, and a child is often just a name
    that points at a group defined elsewhere in the file.
    """
    seen = seen if seen is not None else set()
    if name in seen:
        return []
    seen.add(name)
    members = list(direct.get(name, []))
    for child in children.get(name, []):
        for host in _members(child, direct, children, seen):
            if host not in members:
                members.append(host)
    return members
