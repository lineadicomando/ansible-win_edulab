---
name: win-workman-new-role
description: Use when adding a new software role to the win_workman catalog — covers directory layout, vars/main.yaml schema definition, tasks/main.yaml dispatcher, meta/main.yaml, and documentation
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
    └── main.yaml
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

win_workman_schema_role_name: lineadicomando.win_workman.<schema>
win_workman_schema_dir: <schema>
```

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

```yaml
---
- name: Set schema role context
  ansible.builtin.set_fact:
    win_workman_schema_role_name: lineadicomando.win_workman.<schema>
    win_workman_schema_dir: <schema>

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

Use `install_dep` from `pkg_utils` to install a dependency before dispatching. This preserves `win_workman_schema_role_name` / `win_workman_schema_dir` after the dependency's `set_fact` calls would otherwise overwrite them.

`win_workman_action` passed by the dispatcher is `""` when no action is specified in the task string — use `default('on', true)` (not bare `default('on')`) so the condition fires for both undefined and empty string:

```yaml
---
- name: Install dependency
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: install_dep
  vars:
    win_workman_dep_role: lineadicomando.win_workman.<dep_schema>
  when: win_workman_action | default('on', true) == 'on'

- name: Set schema role context
  ansible.builtin.set_fact:
    win_workman_schema_role_name: lineadicomando.win_workman.<schema>
    win_workman_schema_dir: <schema>

- name: Dispatch to package workflow
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_<schema>_schema }}"
    win_workman_schema_hooks:
      after_install: true
      after_uninstall: true
```

> The `Set schema role context` `set_fact` is required when a dependency is installed first, because the dependency's own `Set schema role context` overwrites `win_workman_schema_role_name` at play scope. Place it immediately before the `pkg_workflow` dispatch.

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

## Step 4 — Documentation

Create `docs/roles/<schema>.md` using the appropriate template:
- `docs/roles/TEMPLATE-software-simple.md` — roles with only on/off/download/info
- `docs/roles/TEMPLATE-software-custom.md` — roles with additional custom actions

Update `docs/index.md` to add the role to the catalog table.

---

## Common schema.package fields

| Field | Type | Purpose |
|-------|------|---------|
| `setup_file` | string | Installer filename (relative to temp dir) |
| `searchName` | string | Registry DisplayName for detection |
| `version` | string | Target version for upgrade comparison |
| `provider` | string | `registry` (default) or `portable` |
| `install_args` | list | Silent install flags |
| `uninstall_args` | list | Silent uninstall flags |
| `before_install_ps_script` | string | PowerShell run before install |
| `after_install_ps_script` | string | PowerShell run after install |
| `before_uninstall_ps_script` | string | PowerShell run before uninstall |
| `after_uninstall_ps_script` | string | PowerShell run after uninstall completes |
| `cleanup_paths` | list | Paths to remove after uninstall |
| `path_dirs` | list | Dirs to add to Windows PATH |
| `product_id` | string | Registry key name used for uninstall (when `searchName` is ambiguous) |
| `uninstall_before_upgrade` | bool | Remove before re-installing (default false) |
| `uninstall_via_helper` | bool | Run uninstall via SYSTEM scheduled task instead of win_package (default false) |
| `portable_dir` | string | Folder name under `win_workman_portable_path` |

---

## Checklist

- [ ] `vars/main.yaml` — schema defined, `win_workman_schema_role_name` and `win_workman_schema_dir` set
- [ ] `tasks/main.yaml` — delegates to `pkg_workflow` (or custom dispatchers + `pkg_workflow`)
- [ ] `tasks/main.yaml` — hooks passed via `vars:` to `pkg_workflow`, not in `defaults/`
- [ ] `tasks/main.yaml` — dependencies use `install_dep`; `set_fact` to restore context placed before `pkg_workflow`
- [ ] `tasks/main.yaml` — action conditions use `default('on', true)` (not bare `default('on')`)
- [ ] `meta/main.yaml` — present
- [ ] `docs/roles/<schema>.md` — created from template
- [ ] `docs/index.md` — role added to catalog table
- [ ] Checksum verified (`sha256sum <installer>`)
- [ ] `searchName` matches actual Windows registry `DisplayName`
