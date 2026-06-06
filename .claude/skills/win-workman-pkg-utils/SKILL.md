---
name: win-workman-pkg-utils
description: Use when working with pkg_utils task includes — covers all available tasks_from values, global defaults, and how to call pkg_utils from custom role actions
---

# pkg_utils Task Includes Reference

## Overview

`pkg_utils` is the shared library role that handles all low-level package operations. Schema roles never implement install/copy/detect logic themselves — they call `pkg_utils` via `include_role` with `tasks_from`.

The entry point for standard workflows is `pkg_workflow`, which internally routes to action-specific tasks.

---

## Global defaults (pkg_utils/defaults/main.yaml)

| Variable | Default | Purpose |
|----------|---------|---------|
| `win_workman_remote_tmp` | `C:\Windows\Temp\ansible` | Temp dir on Windows target |
| `win_workman_storage_path` | `{{ lookup('env', 'HOME') }}/win_workman_storage` | Installer storage on controller |
| `win_workman_portable_path` | `C:\PortableApps` | Root for portable apps on target |
| `win_workman_default_lang` | `en_US` | Locale hint for locale-aware roles |
| `win_workman_mode_title` | `"Maintenance in progress"` | Banner title in lock mode |
| `win_workman_mode_text` | *(multiline)* | Banner body text |
| `win_workman_mode_force_logoff` | `true` | Force logoff on lock |
| `win_workman_restart_timeout` | `600` | Seconds to wait for reboot |
| `win_workman_restart` | `true` | Whether reboots are allowed |

Override these in inventory `group_vars` or play `vars`.

---

## Workflow entry points

### pkg_workflow — standard action router

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_<schema>_schema }}"
```

Routes `win_workman_action` to:

| `win_workman_action` | Routed to |
|---------------------|-----------|
| `on` | `pkg_act_on` |
| `off` | `pkg_act_off` |
| `download` | `pkg_act_download` |
| `copy` | `pkg_act_copy` |
| `info` | `pkg_act_info` |
| `is_present` | `pkg_act_is_present` |

---

## Action task includes

### pkg_act_on — install or upgrade

Detects current state, computes operation (install/upgrade/downgrade/noop), downloads, copies, installs, runs hooks, manages shortcuts and PATH.

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_act_on
  vars:
    win_workman_schema: "{{ win_workman_myrole_schema }}"
```

Registered output: `win_workman_install_result`  
Key facts set: `win_workman_operation`, `win_workman_needs_action`, `win_workman_is_present`

### pkg_act_off — uninstall

Detects presence, runs `before_uninstall_ps_script`, calls `win_package` with `state: absent` (or the PowerShell helper if `uninstall_via_helper: true`), removes cleanup_paths, removes shortcuts, removes PATH entries.

When `uninstall_via_helper: true`, the uninstall string is read from the registry, parsed (handles both `"path" inline-args` and `MsiExec.exe args` formats), and executed via `Start-Process`. Use `uninstall_valid_rc` in the schema to declare which exit codes are treated as success (default `[0]`).

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_act_off
  vars:
    win_workman_schema: "{{ win_workman_myrole_schema }}"
```

### pkg_act_download — controller-side download only

Downloads all files in `schema.files` to `win_workman_storage_path`. Does not copy to Windows target.

### pkg_act_copy — copy to remote temp only

Downloads (if needed) and copies to `win_workman_remote_tmp` on the Windows target. No install.

### pkg_act_info — report state, no changes

Reads registry (or filesystem for portable), reports `win_workman_is_present`, `win_workman_installed_version`, `win_workman_operation`. Sets `changed: false`.

### pkg_act_is_present — assert installed

Fails the play if the software is not installed. Use to verify prerequisites.

---

## Support task includes

### detect_sw — registry detection

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: detect_sw
  vars:
    win_workman_schema: "{{ win_workman_myrole_schema }}"
```

Sets `win_workman_detect_sw.result` with `display_name`, `display_version`, `uninstall_string`.

### info — same as detect_sw + set facts

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: info
```

Sets: `win_workman_is_present` (bool), `win_workman_installed_version` (string).

### download — download files to storage

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: download
```

Uses `win_workman_schema.files[*].{url,filename,checksum}`. Saves to `win_workman_storage_path`.

### win_copy — copy from storage to remote

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: win_copy
```

Copies from `win_workman_storage_path` to `win_workman_remote_tmp` on the Windows host.

### shortcuts — create or remove shortcuts

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: shortcuts
  vars:
    win_workman_schema_shortcuts_state: "present"   # or "absent"
```

Uses `win_workman_schema.shortcuts`.

### win_path — manage Windows system PATH

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: win_path
  vars:
    win_workman_schema_win_path_state: present    # or absent
```

Uses `win_workman_schema.package.path_dirs`.

### win_extract — 7-Zip extraction (high-level)

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: win_extract
  vars:
    win_workman_extract_files: "{{ win_workman_schema.files }}"
    win_workman_remote_extract_path: "{{ win_workman_portable_path }}"
```

Loops over `win_workman_extract_files` and extracts each entry that has `extract: 7z`. Delegates to `7zip` internally. Used by `pkg_act_on` for portable packages.

### 7zip — low-level 7-Zip runner

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: 7zip
  vars:
    win_workman_7zip_command: x          # x = extract with paths, e = flat extract, a = archive
    win_workman_7zip_archive_path: "{{ win_workman_remote_tmp }}\\archive.7z"
    win_workman_7zip_source_path: "C:\\PortableApps\\MyApp"
```

Bootstraps `7zr.exe` + `7za.exe` on the controller, copies them to the Windows target, then runs the requested command. Result registered as `win_workman_7zip`. Prefer `win_extract` for schema-driven extraction; use `7zip` directly only for custom archive operations.

### run_as_system — run executable as SYSTEM

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: run_as_system
  vars:
    win_workman_system_task_exe: "C:\\path\\to\\app.exe"
    win_workman_system_task_name: "win_workman_my_task"   # unique, cleaned up on exit
    win_workman_system_task_args: "/silent"               # optional
    win_workman_system_task_timeout: 180                  # optional, seconds
```

Runs an executable with SYSTEM privileges and highest run level via a temporary Scheduled Task. Result registered as `win_workman_run_as_system_result`.

### start_process — run arbitrary executable

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: start_process
```

### kill — terminate processes by name

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: kill
```

### restart — trigger reboot

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: restart
```

Honors `win_workman_restart` (bool) and `win_workman_restart_timeout` (seconds).

### logoff — force logoff all interactive sessions

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: logoff
```

### profiles — enumerate user profiles

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: profiles
```

Sets `win_workman_profiles` list. Used by roles that need to apply changes per-user (e.g., wallpaper, browser data removal).

### win_clean_temp — clean temp files

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: win_clean_temp
```

Removes files from `win_workman_remote_tmp` after install.

### pending_restart — check for pending reboot

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pending_restart
```

### shortcut_cleaner — remove stale shortcuts

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: shortcut_cleaner
```

### include_tasks — run role-internal task file

Used to call optional hook files (`before_install`, `after_install`) from a schema role:

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: include_tasks
  vars:
    win_workman_schema_tasks: "before_install"
```

Looks for `roles/<schema_dir>/tasks/before_install.yaml`; skips if absent.

### install_dep — install a role dependency, preserving schema context

Installs another schema role as a dependency while saving and restoring `win_workman_schema_role_name` and `win_workman_schema_dir`. Use this instead of calling `include_role` directly, to prevent the dependency's `set_fact` calls from polluting the caller's hook context.

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: install_dep
  vars:
    win_workman_dep_role: lineadicomando.win_workman.chrome   # required
    win_workman_dep_action: "on"                              # optional, default "on"
  when: win_workman_action | default('on', true) == 'on'
```

The save/restore is done via `set_fact`, so it always overrides any stale play-scoped values left by the dependency role.

---

## Typical custom action pattern

When a role implements a custom action (e.g., `rm_data`), it calls pkg_utils support tasks directly:

```yaml
# roles/myrole/tasks/act_rm_data.yaml
---
- name: Enumerate user profiles
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: profiles

- name: Remove application data per profile
  ansible.windows.win_file:
    path: "{{ item.profile_path }}\\AppData\\Local\\MyApp"
    state: absent
  loop: "{{ win_workman_profiles }}"
  loop_control:
    label: "{{ item.username }}"
```

---

## Important: win_workman_schema must be set

All `pkg_utils` workflow tasks read from `win_workman_schema`. Always pass it explicitly:

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: pkg_workflow
  vars:
    win_workman_schema: "{{ win_workman_myrole_schema }}"
```

For custom action tasks that call support includes (e.g., `download`, `shortcuts`), ensure `win_workman_schema` is already set — either pass it in the role vars or set it with `set_fact` before calling the include.
