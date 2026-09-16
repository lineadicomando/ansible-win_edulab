---
name: win-workman-new-role
description: Use when adding a new software role to the win_workman catalog — covers directory layout, vars/main.yaml schema definition, tasks/main.yaml dispatcher, dependency guards, meta/main.yaml and meta/mcp.yaml, and the catalog docs
---

# Adding a New Software Role to win_workman

## Overview

Every installable application is a **schema role**: a thin wrapper that defines the package schema in `vars/main.yaml` and delegates all workflow logic to `pkg_utils` via `include_role`. The role itself contains no install/uninstall logic.

---

## Directory Layout

```
roles/<schema>/
├── defaults/         # omit if no user-overridable vars
│   └── main.yaml
├── tasks/
│   └── main.yaml     # dispatcher — delegates to pkg_utils or custom act_*.yaml
├── vars/
│   └── main.yaml     # schema definition + supporting computed vars
└── meta/
    ├── main.yaml
    └── mcp.yaml      # read by the get_role_info MCP tool
```

For roles with custom actions (e.g., privacy enforcement, data removal), add:
```
tasks/
├── main.yaml
├── act_<custom_action>.yaml
└── ...
```

For roles with install/uninstall hooks, add the relevant hook files:
```
tasks/
├── main.yaml
├── after_install.yaml    # runs after pkg_act_on installs the package
├── after_uninstall.yaml  # runs after pkg_act_off uninstalls the package
└── ...                   # before_install.yaml, before_uninstall.yaml also supported
```

---

## Step 1 — vars/main.yaml (schema definition)

### Simple role (registry installer, single arch)

```yaml
# ==============================================================================
#  Software Information:
#      - Name:        <Display Name>
#      - Homepage:    https://...
#      - Download:    https://...
# ==============================================================================
---
win_workman_<schema>_schema:
  name: <Display Name>
  package:
    setup_file: <installer-filename.exe>
    searchName: "<Registry uninstall display name>"
    version: "<x.y.z>"
    provider: registry          # registry (default) or portable
    install_args:
      - /VERYSILENT             # Inno Setup / NSIS silent flags
    uninstall_args:
      - /VERYSILENT
  files:
    - filename: <installer-filename.exe>
      url: https://...
      checksum: sha256:<hex>
  shortcuts: []                 # omit or leave empty if none needed
```

Add `role: lineadicomando.win_workman.<schema>` inside the schema dict when the role uses
install/uninstall hooks — that field is how `pkg_utils` finds the hook task files. Most
roles in the catalog carry it anyway; it costs nothing and keeps hooks available later.

> **`searchName`** must match the `DisplayName` value in the Windows Uninstall registry key — verify with `Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' | Select DisplayName,DisplayVersion`.

### Portable role (7-Zip extraction)

```yaml
win_workman_<schema>_schema:
  name: <Display Name>
  package:
    provider: portable
    portable_dir: <FolderName>  # relative to win_workman_portable_path
  files:
    - filename: archive.7z
      url: https://...
      checksum: sha256:<hex>
      extract: 7z
      dest_dir: <FolderName>
  shortcuts:
    - description: "<App Name>"
      src: "%ProgramFiles%\\..\\app.exe"
      dest: '%Public%\Desktop\<App Name>.lnk'
      icon: "%ProgramFiles%\\..\\app.exe,0"
      directory: "%ProgramFiles%\\...\\"
```

### Architecture-aware role (32/64-bit)

```yaml
# Computed arch from task argv
win_workman_<schema>_arch: >-
  {{
    "32bit" if (
      "32bit" in (win_workman_task_argv | default([]))
    ) else "64bit"
  }}

win_workman_<schema>_setup_filename:
  64bit: app64.msi
  32bit: app32.msi

win_workman_<schema>_schema:
  name: <Display Name>
  package:
    setup_file: "{{ win_workman_<schema>_setup_filename[win_workman_<schema>_arch] }}"
    searchName: "<Registry Display Name>"
    version: "<x.y.z>"
    provider: registry
    install_args: [/quiet]
    uninstall_args: [/quiet]
  files:
    - filename: "{{ win_workman_<schema>_setup_filename[win_workman_<schema>_arch] }}"
      url: "{{ win_workman_<schema>_url[win_workman_<schema>_arch] }}"
      checksum: "{{ win_workman_<schema>_checksum[win_workman_<schema>_arch] }}"
```

### Per-user role (installer that only installs into the calling user's profile)

Symptom: run elevated over SSH it lands in `C:\Users\maint\AppData\Local\Programs` with an
HKCU uninstall key (Inno Setup `PrivilegesRequired=lowest`, many Electron apps). Give the
schema a `usr` block instead of (or besides) `package`, and `default_action: usr` if it has
no `package`. Field reference: **win-workman-schema**, section *The `usr` block*. `zed` is
the worked example; `tasks/main.yaml` is the simple dispatcher below, unchanged. In
`meta/mcp.yaml` write a `notes` line saying it is per-user (`install_scopes` is derived
automatically by the MCP server).

---

## Step 2 — tasks/main.yaml

### Simple role (no custom actions, no hooks)

```yaml
---
- name: Dispatch to package workflow
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_<schema>_schema }}"
```

### Role with custom actions

Dispatch the custom action first, then fall through to `pkg_workflow` for everything else.
`veyon` is the worked example in the catalog.

```yaml
---
- name: Dispatch action my_action
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.<schema>
    tasks_from: act_my_action
  when: win_workman_action == "my_action"

- name: Dispatch to package workflow
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_<schema>_schema }}"
  when: win_workman_action not in ["my_action"]
```

### Role with install/uninstall hooks

Pass `win_workman_schema_hooks` as `vars:` directly to the `pkg_workflow` call — **not** in `defaults/main.yaml`. This scopes the hooks to the role's own workflow and prevents them from bleeding into dependency roles called beforehand.

```yaml
---
- name: Dispatch to package workflow
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_<schema>_schema }}"
    win_workman_schema_hooks:
      after_install: true    # requires tasks/after_install.yaml
      after_uninstall: true  # requires tasks/after_uninstall.yaml
```

Each hook file is a standard task list. Use `win_workman_install_result.changed` / `win_workman_uninstall_result.changed` / `win_workman_uninstall_via_helper_result.changed` to guard conditional steps:

```yaml
# tasks/after_install.yaml
---
- name: Reboot after install
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: restart
  when: win_workman_install_result.changed | default(false) | bool
```

```yaml
# tasks/after_uninstall.yaml
---
- name: Reboot after uninstall
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: restart
  when: >-
    (win_workman_uninstall_result.changed | default(false) | bool)
    or (win_workman_uninstall_via_helper_result.changed | default(false) | bool)
```

### Role with a dependency on another schema role

Include the dependency role directly — there is no `install_dep` helper in `pkg_utils`:

```yaml
---
# win_workman_dep: lineadicomando.win_workman.<dep_schema>
- name: Install dependency <dep_schema>
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.<dep_schema>
  vars:
    win_workman_action: "on"
  when:
    - (win_workman_task.act | default('on', true)) == 'on'
    - "'nodep' not in (win_workman_task_argv | default([]))"

- name: Dispatch to package workflow
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_<schema>_schema }}"
```

Two things in that guard are easy to get wrong, and both have been bugs:

- Guard on **`win_workman_task.act`**, not `win_workman_action`. Vars passed to
  `include_role` persist in the play, so after the dependency has been included with
  `win_workman_action: "on"` every later task in the run sees that value and
  `<schema>-info` would install the dependency too. The dispatcher reassigns
  `win_workman_task` on each loop iteration.
- Use **`default('on', true)`**, not bare `default('on')`. A bare task string like
  `winfsp` parses with `act` as the empty string, which a plain `default` leaves alone.

The `# win_workman_dep:` comment is the marker the catalog docs are generated from — keep
it. The `nodep` condition lets `<schema>-on-nodep` skip the dependency.

Hooks stay correct across a dependency without any extra work, because `include_tasks`
resolves the hook file from `win_workman_schema.role` — a field of the schema dict passed
to `pkg_workflow` — not from a play-scoped fact. `gcpw` is the worked example: dependency
on `chrome`, plus `after_install` and `after_uninstall`.

---

## Step 3 — meta/main.yaml

```yaml
---
galaxy_info:
  author: lineadicomando
  description: win_workman <schema> role
  license: MIT
  min_ansible_version: "2.15"
  platforms:
    - name: Windows
      versions: ["all"]
dependencies: []
```

---

## Step 4 — meta/mcp.yaml

This is what the `get_role_info` MCP tool reads. 77 of the roles have one; a role without
it is invisible to anyone asking "what options does `<schema>` have". Only needed for
roles with custom actions or user-facing defaults, but cheap to write.

```yaml
---
display_name: <Display Name>
custom_actions:
  - name: <action>
    description: <what it does>
defaults:
  - var: win_workman_<schema>_<option>
    type: bool          # bool | str | list | int
    default: false
    description: <what it controls>
notes: >
  Operational guidance — when to prefer the standalone playbook over run_tasks, or
  which action to use for an incremental update.
```

---

## Step 5 — Documentation

Create `docs/roles/catalog/<schema>.md` from the appropriate template:
- `docs/roles/TEMPLATE-software-simple.md` — roles with only on/off/download/info
- `docs/roles/TEMPLATE-software-custom.md` — roles with additional custom actions

Core and management roles live in `docs/roles/core/` and `docs/roles/management/`
instead. Update `docs/index.md` to add the role to the catalog table.

The catalog doc carries an `Installer:` line repeating the setup filename — it has to be
re-edited on every version bump. See **win-workman-pkg-update**.

---

For the full list of `schema.package` fields and what each one does, see
**win-workman-schema** — it is not repeated here.

---

## Checklist

- [ ] `vars/main.yaml` — `win_workman_<schema>_schema` defined; `role:` set if the role uses hooks
- [ ] `tasks/main.yaml` — delegates to `pkg_workflow` (or custom dispatchers + `pkg_workflow`)
- [ ] `tasks/main.yaml` — hooks passed via `vars:` to `pkg_workflow`, not in `defaults/`
- [ ] `tasks/main.yaml` — dependencies guard on `(win_workman_task.act | default('on', true)) == 'on'`, with the `# win_workman_dep:` marker comment
- [ ] `meta/main.yaml` — present
- [ ] `meta/mcp.yaml` — present if the role has custom actions or user-facing defaults
- [ ] `docs/roles/catalog/<schema>.md` — created from template
- [ ] `docs/index.md` — role added to catalog table
- [ ] Checksum verified (`sha256sum <installer>`)
- [ ] `searchName` matches actual Windows registry `DisplayName`
- [ ] per-user role: `usr.uninstall_key` read from HKCU after a manual install, `setup_file` matches a `files` entry with sha256, tested with a copy of `tests/usr_zed.yaml`
