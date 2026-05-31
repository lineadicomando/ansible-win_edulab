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
    groups: dict = {}
    _walk(raw.get("all", {}), hosts, groups)
    return {"hosts": hosts, "groups": groups}


def _walk(node: dict, hosts: dict, groups: dict, group_name: str = None):
    for host, vars_ in (node.get("hosts") or {}).items():
        if host not in hosts:
            hosts[host] = vars_ or {}
        if group_name:
            groups.setdefault(group_name, [])
            if host not in groups[group_name]:
                groups[group_name].append(host)

    for child_name, child_node in (node.get("children") or {}).items():
        _walk(child_node or {}, hosts, groups, child_name)
