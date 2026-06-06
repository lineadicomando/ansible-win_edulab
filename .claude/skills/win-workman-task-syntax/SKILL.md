---
name: win-workman-task-syntax
description: Use when writing, parsing, or debugging win_workman task strings — covers the schema-action-arg syntax, the parse_tasks filter, dispatcher variables, and all standard and role-specific actions
---

# win_workman Task String Syntax

## Format

```
<schema>[-<action>[-<arg1>[-<arg2>…]]]
```

- **schema** — role name (e.g., `chrome`, `vscode`, `veyon`)
- **action** — operation to perform; defaults to `on` when omitted
- **args** — zero or more positional arguments passed to the role

### Examples

| Task string | schema | action | args |
|-------------|--------|--------|------|
| `chrome` | chrome | *(default)* | [] |
| `chrome-off` | chrome | off | [] |
| `chrome-on-32bit` | chrome | on | [32bit] |
| `vscode-download` | vscode | download | [] |
| `veyon-config-student` | veyon | config | [student] |
| `wu-pause` | wu | pause | [] |
| `wallpaper-set` | wallpaper | set | [] |
| `python313-on` | python313 | on | [] |

> **Note:** for `veyon-config`, the task arg (`student`, `teacher`, etc.) is parsed and available in `win_workman_task_argv` but is **not read** by `act_config.yaml`. Master vs agent role is controlled by `win_workman_veyon_master` (bool variable), not by the task string argument.

---

## How the dispatcher works

The `dispatcher` role calls the `parse_tasks` filter (Python plugin) to convert task strings into structured dicts, then loops and includes each schema role:

```yaml
# roles/dispatcher/tasks/main.yaml
- ansible.builtin.include_role:
    name: "lineadicomando.win_workman.{{ _wm_item.schema }}"
  vars:
    win_workman_action:    "{{ _wm_item.act }}"     # e.g., "on"
    win_workman_task_argv: "{{ _wm_item.argv }}"    # e.g., ["chrome", "on", "32bit"]
    win_workman_task_argc: "{{ _wm_item.argc }}"    # e.g., 3
    win_workman_task:      "{{ _wm_item }}"         # full parsed dict
  loop: "{{ _win_workman_tasks_parsed }}"
  loop_control:
    loop_var: _wm_item
    label: "{{ _wm_item.task }}"
```

### Parsed dict structure

```python
{
  "task":   "chrome-on-32bit",   # original string
  "schema": "chrome",            # token[0]
  "act":    "on",                # token[1], or "" if absent
  "argc":   3,                   # total token count
  "argv":   ["chrome", "on", "32bit"]  # all tokens
}
```

> **`act` is `""` (empty string) when no action is specified** — e.g. `chrome`, `vscode`.
> `pkg_workflow` resolves the effective action as `win_workman_action or win_workman_schema.default_action`.
> In role task files, always use `default('on', true)` (not bare `default('on')`) when comparing
> against action strings, so the fallback fires for both undefined and empty string:
>
> ```yaml
> when: win_workman_action | default('on', true) == 'on'
> ```

### Reading args in a role

```yaml
# Check if "32bit" was passed
win_workman_chrome_arch: >-
  {{
    "32bit" if ("32bit" in (win_workman_task_argv | default([])))
    else "64bit"
  }}

# Read the 3rd token (argv[2])
win_workman_some_arg: "{{ win_workman_task_argv[2] | default('default_value') }}"
```

---

## Standard actions (handled by pkg_utils)

| Action | What it does |
|--------|--------------|
| `on` | Install or upgrade to schema version |
| `off` | Uninstall |
| `download` | Download installer to controller storage only |
| `copy` | Copy installer to remote temp, no install |
| `info` | Report installed version/state, no changes |
| `is_present` | Fail if software is not installed |

---

## Role-specific actions

### Browsers (chrome, firefox)

| Action | What it does |
|--------|--------------|
| `privacy_on` | Apply Group Policy privacy restrictions |
| `privacy_off` | Remove privacy restrictions |
| `rm_data` | Delete all user browser data |

### Wallpaper

| Action | What it does |
|--------|--------------|
| `on` | Copy wallpaper file to target (same as `set`) |
| `off` | Remove deployed wallpaper file |
| `set` | Apply wallpaper to all user profiles |
| `reset` | Restore default Windows wallpaper |
| `lock` | Prevent users from changing wallpaper |
| `unlock` | Allow users to change wallpaper |
| `clear_history` | Remove wallpaper history from registry |

### Windows Update (wu)

| Action | What it does |
|--------|--------------|
| `run` | Search, download and install available updates |
| `on` | Resume Windows Update (alias for `resume`) |
| `off` | Pause Windows Update at max duration (alias for `pause` at max) |
| `pause` | Pause updates for `win_workman_wu_pause_days` days (default 7) |
| `resume` | Resume paused updates |
| `max_pause_days` | Read or set `FlightSettingsMaxPauseDays`; without args reports current value, with a duration sets the cap |
| `is_paused` | Check if updates are paused; sets `win_workman_wu_is_paused` fact |
| `policy_standard` | Restore standard WU Group Policy |
| `policy_ansible_managed` | *(deprecated)* Raises an error |

### Veyon

| Action | What it does |
|--------|--------------|
| `on` | Install Veyon service |
| `off` | Uninstall Veyon service |
| `config` | Configure RSA keys and network objects; master vs agent role set via `win_workman_veyon_master` variable, not by task arg |

### Safe Exam Browser (seb)

| Action | What it does |
|--------|--------------|
| `on` | Install SEB |
| `off` | Uninstall SEB |
| `deploy` | Deploy a `.seb` config file to target |
| `undeploy` | Remove `.seb` config file |
| `config_key` | Report the Config Key for a `.seb` file |

### Lock / Autologon / Session

| Role | `on` | `off` |
|------|------|-------|
| `lock` | Enable maintenance mode (banner + login restriction) | Disable maintenance mode |
| `autologon` | Enable automatic logon | Disable automatic logon |
| `ms_account` | Block Microsoft account sign-in | Allow Microsoft account sign-in |

---

## Calling the dispatcher from a playbook

```yaml
- name: Manage workstations
  hosts: classroom
  roles:
    - role: lineadicomando.win_workman.dispatcher
      vars:
        win_workman_tasks:
          - chrome-on-64bit
          - vscode
          - wallpaper-lock
          - wu-pause
```

Or via task include:

```yaml
- name: Deploy software
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.dispatcher
  vars:
    win_workman_tasks:
      - chrome
      - firefox-off
      - veyon-config
```

---

## Using the parse_tasks filter directly

```yaml
- name: Parse task strings
  ansible.builtin.set_fact:
    _parsed: "{{ ['chrome-on-32bit', 'vscode', 'wu-pause'] | lineadicomando.win_workman.parse_tasks }}"
```

Returns:
```json
[
  {"task": "chrome-on-32bit", "schema": "chrome", "act": "on", "argc": 3, "argv": ["chrome", "on", "32bit"]},
  {"task": "vscode", "schema": "vscode", "act": "", "argc": 1, "argv": ["vscode"]},
  {"task": "wu-pause", "schema": "wu", "act": "pause", "argc": 2, "argv": ["wu", "pause"]}
]
```

---

## Debugging task parsing

If a task string isn't dispatching correctly:

1. Check that `schema` maps to an existing role: `roles/<schema>/tasks/main.yaml` must exist.
2. Verify `win_workman_action` is being checked correctly in the role's `tasks/main.yaml`.
3. Role-specific actions must be explicitly dispatched *before* the fallback `pkg_workflow` include, with `when: win_workman_action == "my_action"`.
4. Schema roles that don't handle `win_workman_action` routing (simple roles) always call `pkg_workflow`, which internally routes standard actions.
