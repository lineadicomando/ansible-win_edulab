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

## Base playbook structure — one workflow step

Every playbook in `playbooks/` is one step that a cockpit-fleet workflow can
chain, and imports the shared body `playbooks/tasks/wf_step.yaml`:

```yaml
---
# <What it does, in a sentence or two.>
#
# Workflow: <where it goes in a workflow, links that matter>
# Survey: <var> (<type>, <default>) <meaning>     — what is worth asking at launch
# Passes on: wf_hosts, wf_unreachable, wf_failed (see tasks/wf_step.yaml)
- name: <Human-readable description>
  hosts: "{{ wf_hosts | default(target_hosts | default('win_managed' if 'win_managed' in groups else 'lab_win')) }}"
  gather_facts: false
  tasks:
    - name: <Action>
      ansible.builtin.import_tasks: tasks/wf_step.yaml
      vars:
        wf_step: <name used in wf_failed>
        wf_step_tasks:
          - "<task>"
```

`wf_step.yaml` adds a reachability gate, a block whose rescue records the hosts
that fail, `set_stats` of `wf_hosts`/`wf_unreachable`/`wf_failed`, and — unless
`wf_tolerant` is true — fails those hosts at the end, so a run by hand fails as
before. Its header documents the optional inputs: `wf_wake` (Wake-on-LAN
first), `wf_step_mark`/`wf_step_unmark` (a host list passed on, as `wf_locked`),
`wf_step_publish` (a per-host fact passed on, as `wf_wu_report`).

Rules:
- `gather_facts: false` **always** — Windows PCs do not need Ansible facts
- `hosts` uses the pattern above: `wf_hosts` from the previous workflow step,
  else `-e target_hosts`, else the default group; `-l` narrows it
- No inline task logic — the work is win_workman task strings
- A task string built from a survey answer is checked first with an
  `assert` (`run_once: true`) against the values the role accepts
- List variables cannot come from a survey (text, number, choice, yes/no): take
  a comma-separated string and split it, or leave the list to the inventory
- Names passed on start with `wf_`: what a step passes on wins over the survey
  of the next one
- Never call `wol` through the dispatcher: the dispatcher sets the remote tmp
  ACL first, which needs the host awake. Use `wf_wake: true`

---

## Dispatcher playbook — win_wm.yaml

`playbooks/win_wm.yaml` runs any task strings given in `t`, on `win_managed`
(or `target_hosts`); a `wol` in `t` becomes `wf_wake`:

```bash
ansible-playbook playbooks/win_wm.yaml -i inventories/school/hosts.yaml \
  -l students -e "t=chrome,vscode"
ansible-playbook playbooks/win_wm.yaml -l teacher -e "t=wol,chrome-off"
```

Via MCP use `run_tasks` instead (it calls the collection's playbook directly) —
see the **win-edulab-mcp** skill.

---

## Available playbooks

The catalogue, the `wf_*` variables and example workflows for cockpit-fleet
are in `docs/playbooks.md`. In short:

| Group | Playbooks |
|---|---|
| Power | `wol`, `maint_restart`, `shutdown` |
| Maintenance | `maint_lock`, `maint_unlock`, `maint_chkdsk`, `maint_wim_scan`, `maint_wim_repair`, `maint_sfc`, `maint_optimize`; `maintenance` (all in one run, for the CLI) |
| Windows Update | `wu_scan`, `wu_run`, `wu_optional`, `wu_pause`, `wu_resume`, `wu_sync_ui` |
| Information | `sysinfo`, `wf_report` (last step of a workflow, on localhost) |
| Software / config | `software`, `win_wm`, `lab_cad`, `lab_coding`, `veyon`, `domain_join`, `gcpw`, `autologon`, `seb_classroom`, `win_iso_build` |

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
| `wf_tolerant` | Step succeeds even when hosts fail; set on workflow step templates |
| `wf_connect_timeout` | Seconds the gate waits for each host (30) |
| `win_workman_*` | Role-specific configuration variables |

---

## Running against a non-default inventory

```bash
ansible-playbook playbooks/win_wm.yaml \
  -i inventories/<lab>/hosts.yaml \
  -l students \
  -e "t=chrome"
```

The default inventory is `school` (from `ansible.cfg`). Always specify `-i inventories/<lab>/hosts.yaml` for all other labs.

---

## Checklist for a new playbook

- [ ] File extension is `.yaml`
- [ ] Header: what it does, `Workflow:`, `Survey:`, `Passes on:`
- [ ] `gather_facts: false`
- [ ] `hosts` with the `wf_hosts | default(target_hosts | default(...))` pattern
- [ ] Imports `tasks/wf_step.yaml` with `wf_step` and `wf_step_tasks`
- [ ] Survey answers that shape a task string are checked by an `assert`
- [ ] Listed in `docs/playbooks.md` (catalogue, and a workflow if it belongs to one)
- [ ] Saved in `playbooks/` if reusable, in `local/` if site-specific, in `tests/` if it is a test sequence
