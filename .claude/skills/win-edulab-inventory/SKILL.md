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
│   └── windows11/
│       └── vars.yaml                   # variables specific to Windows 11 hosts
└── host_vars/
    └── <HOSTNAME>.yaml                 # per-host overrides (e.g. DOC.yaml)
```

---

## Group hierarchy in hosts.yaml

```yaml
all:
  children:
    servers:          # Linux servers (samba-ad-dc)
    teachers:         # teacher PC(s)
    students:         # student PCs
    lab_win:          # all Windows PCs in the lab (teachers + students)
    lab_cad:          # same hosts as lab_win — semantic alias for CAD lab playbooks
    lab_coding:       # same hosts as lab_win — semantic alias for coding lab playbooks
    windows11:        # all Windows 11 hosts
```

Groups `lab_win`, `lab_cad`, `lab_coding`, `windows11` reference the same hosts — never duplicate them, use them as semantic aliases for targeting playbooks.

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
2. Reference it in the logical groups (`lab_win`, `windows11`, etc.)
3. If needed, create `host_vars/<HOSTNAME>.yaml` for host-specific overrides

```yaml
# hosts.yaml — example: adding a student
students:
  hosts:
    student03:
      ansible_host: 172.16.2.13
      ansible_mac: 52:54:00:xx:xx:xx
lab_win:
  hosts:
    student03:
windows11:
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
