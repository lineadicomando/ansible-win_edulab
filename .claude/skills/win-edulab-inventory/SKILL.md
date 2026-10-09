---
name: win-edulab-inventory
description: Use when reading, writing, or debugging inventory files for this project — covers multi-lab layout, group hierarchy, host_vars, group_vars split, and file naming conventions
---

# Inventories — win-edulab project

## Conventions

- All YAML files use the **`.yaml`** extension (never `.yml`)
- Default inventory is `inventories/school/hosts.yaml` (set in `ansible.cfg`)
- For any other lab always pass `-i inventories/<lab>/hosts.yaml` or `inventory=<lab>` via MCP

---

## Available labs

| Inventory | Description |
|-----------|-------------|
| `school`        | Default lab — local dev/test environment |
| `ario_info`     | Informatics lab — Ario campus |
| `ario_ling`     | Language lab — Ario campus |
| `spalla_info1`  | Informatics lab 1 — Spalla campus |
| `spalla_info2`  | Informatics lab 2 — Spalla campus |
| `spalla_ling`   | Language lab — Spalla campus |
| `spalla_aule`   | Classroom PCs — Spalla campus. Flat `aule` group, no teachers/students split, per-host `ansible_user` |

Only `school` is tracked by git; `.gitignore` excludes `inventories/*` and re-includes it.
The site inventories exist locally only.

---

## Structure of each inventory

```
inventories/<lab>/
├── hosts.yaml                          # hosts and groups
├── group_vars/
│   ├── all/
│   │   ├── vars.yaml                   # plaintext variables (shared across all hosts)
│   │   └── vault.yaml                  # secrets encrypted with Ansible Vault
│   ├── teachers/
│   │   └── vars.yaml                   # variables specific to teacher PCs
│   ├── students/
│   │   └── vars.yaml                   # variables specific to student PCs
│   └── lab_win/
│       └── vars.yaml                   # SSH/PowerShell connection settings for the Windows PCs
└── host_vars/
    └── <HOSTNAME>.yaml                 # per-host overrides (e.g. DOC.yaml)
```

---

## Group hierarchy in hosts.yaml

```yaml
all:
  children:
    servers:          # Linux servers (dc01)
    teachers:         # teacher PC(s)
    students:         # student PCs
    lab_cad:          # vertical: the PCs of the CAD lab, listed directly
    lab_coding:       # vertical: the PCs of the coding lab, listed directly
    lab_win:          # transversal: every Windows PC, built from other groups
    samba_dc:         # the DC again (dc01): required by lineadicomando.samba_dc
```

Three kinds of group, each answering a different question:

- **Role** (`servers`, `teachers`, `students`) — what the machine is. Hosts are declared
  here, once, with `ansible_host` and `ansible_mac`.
- **Vertical** (`lab_cad`, `lab_coding`) — which lab the PC sits in. They list hosts
  directly; real labs rarely share machines.
- **Transversal** (`lab_win`) — every Windows PC whatever its lab. Built with `children`,
  never by repeating hosts. It carries the connection settings and is the default target
  of the lab-wide playbooks.

`school` builds `lab_win` from the labs:

```yaml
lab_win:
  children:
    lab_cad:
    lab_coding:
```

The site inventories hold one lab each, so they have no vertical groups and build it
from the roles:

```yaml
lab_win:
  children:
    teachers:
    students:
```

`spalla_aule` is the exception: no roles, and `lab_win` lists directly the PCs that are
managed. There is no `windows11` group any more: its variables moved to
`group_vars/lab_win`. Add a version group only where a play really needs one.

Variables set on a child group win over those of its parents, so `teachers`/`students`
(or the lab groups) override `lab_win` on a clash.

---

## Required variables per host

Defined in `group_vars/all/vars.yaml`:

```yaml
ansible_user: maint
ansible_password: "{{ ansible_vault_password }}"
ansible_become_password: "{{ ansible_vault_become_password }}"
ansible_domain: "<domain>"
ansible_ssh_pub_key_path: ~/.ssh/id_ed25519.pub
ansible_ssh_common_args: "-i {{ ansible_ssh_pub_key_path }} -o StrictHostKeyChecking=no ..."
```

Sensitive values (passwords) are always **referenced from the vault** — never written in plaintext in `vars.yaml`.

---

## Group-specific variables

`group_vars/teachers/vars.yaml`:
```yaml
win_workman_veyon_master: true
win_workman_veyon_labs:
  - lab_win
```

`group_vars/students/vars.yaml`:
```yaml
win_workman_veyon_master: false
```

---

## Adding a new host

1. Add it to `hosts.yaml` in the right group with `ansible_host` and `ansible_mac`
2. In an inventory with vertical groups, name it in its lab group too. `lab_win` picks it up through `children`
3. If needed, create `host_vars/<HOSTNAME>.yaml` for host-specific overrides

```yaml
# hosts.yaml — example: adding a student
students:
  hosts:
    student03:
      ansible_host: <IP in the lab subnet>   # see ansible_subnet in group_vars/all
      ansible_mac: <NIC MAC, needed by wol>
lab_coding:           # only where the inventory has lab groups
  hosts:
    student03:
```

---

## Adding a new inventory (new lab)

Copy the structure from an existing inventory and adapt:
1. `hosts.yaml` — real IPs and MACs for the machines
2. `group_vars/all/vars.yaml` — lab-specific variables (e.g. browser URL)
3. `group_vars/all/vault.yaml` — encrypt passwords with `ansible-vault encrypt <file>`

See the **win-edulab-vault** skill for secret management.
