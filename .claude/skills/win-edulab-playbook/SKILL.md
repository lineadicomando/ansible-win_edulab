---
name: win-edulab-playbook
description: Use when writing or reviewing playbooks for this project — covers file naming, gather_facts, target_hosts pattern, role-based style, playbooks vs tests directory distinction
---

# Playbook patterns — win-edulab project

## Conventions

- All YAML files use the **`.yaml`** extension (never `.yml`)
- `playbooks/` — reusable playbooks, safe to run in production
- `tests/` — test sequences combining snapshot revert + WoL + operations; development/validation only

---

## Base playbook structure

```yaml
---
- name: <Human-readable description>
  hosts: "{{ target_hosts | default('<default_group>') }}"
  gather_facts: false
  roles:
    - role: lineadicomando.win_workman.dispatcher
      vars:
        win_workman_tasks:
          - "<task>"
```

Rules:
- `gather_facts: false` **always** — Windows PCs do not need Ansible facts
- `hosts` **always** uses the `{{ target_hosts | default('<group>') }}` pattern to allow override via `-e target_hosts=<host>`
- Use `roles:` rather than inline `tasks:` — delegate all work to the collection

---

## Dispatcher playbook — win_wm.yaml

The main playbook for software management is `playbooks/win_wm.yaml`. It receives tasks via the `t` variable:

```bash
# CLI — multiple tasks
ansible-playbook playbooks/win_wm.yaml -i inventories/school/hosts.yaml \
  -l students -e "t=chrome,vscode"

# CLI — single task
ansible-playbook playbooks/win_wm.yaml -l teacher -e "t=chrome-off"
```

Via MCP use `run_tasks` instead of calling the playbook directly — see the **win-edulab-mcp** skill.

---

## Available standalone playbooks

| File | Default target | Purpose |
|------|---------------|---------|
| `playbooks/win_wm.yaml` | passed via `-l` | Software dispatcher (all win_workman tasks) |
| `playbooks/veyon.yaml` | `lab_win` | Full Veyon setup (keypair + config + network objects) |
| `playbooks/seb_classroom.yaml` | `students` | SEB configuration for Google Classroom |
| `playbooks/autologon.yaml` | `lab_win` | Hardcoded autologon with restart |
| `playbooks/wol.yaml` | `lab_win` | Wake-on-LAN broadcast |
| `playbooks/lab_cad.yaml` | `lab_cad` | CAD lab setup |
| `playbooks/lab_coding.yaml` | `lab_coding` | Coding lab setup |

> **Note on autologon**: prefer `run_tasks(["autologon"])` with `e` vars for full control. `autologon.yaml` is a fixed shortcut that hardcodes `win_workman_autologon_restart: true` and targets `lab_win`.

---

## import_playbook pattern in tests

Files in `tests/` chain multiple plays with `import_playbook`:

```yaml
---
- name: Revert to baseline
  ansible.builtin.import_playbook: virsh.yaml
  vars:
    vm: teacher
    cmd: snapshot-revert
    snapshot: baseline

- name: Wake host
  ansible.builtin.import_playbook: ../playbooks/wol.yaml
  vars:
    target_hosts: teacher

- name: Test packages
  hosts: teacher
  gather_facts: false
  roles:
    - role: lineadicomando.win_workman.dispatcher
      vars:
        win_workman_tasks:
          - "<role>"
```

---

## Common extra vars

| Variable | Purpose |
|----------|---------|
| `target_hosts` | Override target group (`-e target_hosts=student01`) |
| `t` | Task list for win_wm.yaml (`-e "t=chrome,vscode"`) |
| `win_workman_*` | Role-specific configuration variables |

---

## Running against a non-default inventory

```bash
ansible-playbook playbooks/win_wm.yaml \
  -i inventories/ario_info/hosts.yaml \
  -l students \
  -e "t=chrome"
```

The default inventory is `school` (from `ansible.cfg`). Always specify `-i inventories/<lab>/hosts.yaml` for all other labs.

---

## Checklist for a new playbook

- [ ] File extension is `.yaml`
- [ ] `gather_facts: false`
- [ ] `hosts: "{{ target_hosts | default('<group>') }}"`
- [ ] Uses `roles:` with `lineadicomando.win_workman.dispatcher`
- [ ] No inline task logic — all work delegated to the collection
- [ ] Saved in `playbooks/` if reusable, in `tests/` if it is a test sequence
