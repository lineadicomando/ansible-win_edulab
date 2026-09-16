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
| `win_workman_cleanup_uninstaller_dir` | `true` | After a successful uninstall, remove the install directory when only the uninstaller's own files are left — Inno Setup cannot delete the running `unins000.exe`. Applies to every package role, and only fires once the detect reports the package gone |

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
| `shortcuts` | `pkg_act_shortcuts` |
| `is_present` | `pkg_act_is_present` |
| `usr` | `pkg_act_usr` → `pkg_usr_<verb>` (per-user deferred install) |

The accepted set is `win_workman_pkg_actions` in `pkg_utils/vars/main.yaml`; anything else
fails with *Unknown action*, listing the valid values.

Before routing, *Validate install scope* refuses `usr` on a schema without a `usr` block
and every other action except `download` on a schema that has only a `usr` block.

---

## Per-user deferred install (`usr`) — file map

Read this instead of the files; the collection doc `docs/roles/core/pkg_utils.md`
(section *Per-user deferred install*) has the design rationale.

| File | Role |
|---|---|
| `tasks/pkg_act_usr.yaml` | parse verb/targets from `win_workman_task_argv`, validate, build `win_workman_usr_policy_base`, include `pkg_usr_<verb>` |
| `tasks/pkg_usr_stage.yaml` | dir tree + ACL (Users RX only), copy agent, register `\win_workman\usr-agent` task (principal `S-1-5-32-545`, AtLogOn, Parallel) |
| `tasks/pkg_usr_policy.yaml` | merge targets into `policies\<schema>.json`; names → SID, kind via `LookupAccountSid` |
| `tasks/pkg_usr_on.yaml` | download → stage → payload copy → policy `present` → prune other versions |
| `tasks/pkg_usr_off.yaml` | stage → policy `absent` (all entries when no targets) |
| `tasks/pkg_usr_info.yaml` | per profile: HKU or `reg load` of NTUSER.DAT, uninstall key + receipt |
| `tasks/pkg_usr_apply.yaml` | `Start-ScheduledTask`, wait on `HKU\<sid>\Software\win_workman\usr\LastRun` |
| `tasks/pkg_usr_purge.yaml` | remove policy + payload; last policy → remove task and tree |
| `files/usr_agent.ps1` | runs as the user: per policy install/upgrade/uninstall, writes receipt |

- Host layout: `C:\ProgramData\win_workman\usr\{agent.ps1, policies\, payload\<schema>\<version>\}`.
- Receipt per user: `HKCU\Software\win_workman\usr\<schema>` (`State`, `Result`, `Changed`,
  `Version`, `Message`, `Timestamp` UTC) + `LastRun` on the parent key; log in
  `%LOCALAPPDATA%\win_workman\usr-agent.log`.
- Registered facts: `win_workman_usr_policy_result`, `win_workman_usr_info`,
  `win_workman_usr_apply_result`, `win_workman_usr_purge_result` (all `.result`).
- Vars: `win_workman_usr_path`, `win_workman_usr_targets` (`[BUILTIN\Users]`),
  `win_workman_usr_timeout`, `win_workman_usr_apply_timeout` (defaults);
  `win_workman_usr_verbs`, `win_workman_usr_target_pattern`, `win_workman_usr_task_path/name` (vars).
- `win_powershell` results with nested objects need `depth: 5`; the default 2 returns type names.

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

When `uninstall_via_helper: true`, the uninstall string is read from the registry, parsed (handles both `"path" inline-args` and `MsiExec.exe args` formats), and executed via `Start-Process -Wait`. Use `uninstall_valid_rc` in the schema to declare which exit codes are treated as success (default `[0]`). **NSIS installers require this flag** — `win_package` returns as soon as `Uninstall.exe` relaunches itself from `%TEMP%`, so the uninstall is reported done while it is still running.

Order of the cleanup tail, which matters because each step reads the one before:

1. `Detect software after uninstall task` — refreshes `win_workman_detect_sw`
2. `Cleanup registry key` — only when `cleanup_registry_key: true` and the entry survived
3. `Detect software after registry key cleanup` — re-runs the detect, but only when step 2 actually changed something
4. `Cleanup paths` — guarded by `win_workman_detect_sw.result.id is none`
5. `Cleanup uninstaller leftovers` — guarded by `not …result.installed`

Step 3 exists because steps 4 and 5 decide from the detect whether the package is really gone, and step 2 invalidates it. Without the refresh both are skipped exactly when the uninstaller keeps its own registry key — which is the case `cleanup_registry_key` is for.

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

### pkg_act_shortcuts — re-create shortcuts only

Applies `schema.shortcuts` with `state: present` without running the install workflow.
Restores Desktop and Start Menu entries on an already installed package. Removal stays
with `off`, which includes the same tasks with `state: absent`.

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

### services_stop — stop schema services before install/uninstall

Stops every service in `win_workman_schema.services` that exists, so the installer can
replace files the service processes hold locked. Silent installers usually skip locked
files without reporting an error, leaving a mix of old and new binaries. `pkg_act_on`
brings the services back to their declared state afterwards.

### detect_lang — pick a language code from the host locale

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: detect_lang
  vars:
    win_workman_detect_lang_allowed: [en_US, it_IT]   # required
    win_workman_detect_lang_map: {}                   # optional BCP47 → code overrides
```

Reads `Get-WinSystemLocale`, `Get-SystemPreferredUILanguage`, `Get-UICulture` and
`Get-Culture`, then resolves each candidate through `lang_map` → `replace('-','_')` →
ISO 639-1 base code, taking the first hit in `allowed`. Writes `win_workman_default_lang`,
leaving it unchanged when nothing matches.

### registry_read — read a single registry value

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: registry_read
  vars:
    win_workman_winreg_path: 'HKLM\SOFTWARE\Vendor\App'
    win_workman_winreg_name: InstallPath
```

Normalises the hive prefix, so `HKLM\...`, `HKLM:\...` and `Registry::HKEY_LOCAL_MACHINE\...`
all work.

### se_read — read a user-rights assignment

```yaml
- ansible.builtin.include_role:
    name: lineadicomando.win_workman.pkg_utils
    tasks_from: se_read
  vars:
    win_workman_se_read_right: SeDenyInteractiveLogonRight
```

Exports `USER_RIGHTS` with `secedit /export` and returns the SIDs/accounts assigned to the
named right. Used by `lock` for the maintenance-mode logon restriction.

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

---

## Role dependencies — not a pkg_utils include

There is **no `install_dep` task include**. A schema role that needs another one installs
it with a plain `include_role` on the dependency, guarded so it only fires for the install
action:

```yaml
# roles/winfsp/tasks/main.yaml
# win_workman_dep: lineadicomando.win_workman.virtiogt
- name: Install dependency virtiogt
  ansible.builtin.include_role:
    name: lineadicomando.win_workman.virtiogt
  vars:
    win_workman_action: "on"
  when: (win_workman_task.act | default('on', true)) == 'on'
```

The guard reads **`win_workman_task.act`**, not `win_workman_action`. Both details matter:

- `act` is `""` for a bare task string like `winfsp`, so `default('on', true)` is required —
  a bare `default('on')` leaves the empty string and the dependency never installs.
- `win_workman_action` cannot be used: vars passed to `include_role` persist in the play, so
  once a dependency has been included with `win_workman_action: "on"` every later task in
  the same run sees that value, and `winfsp-info` would install the dependency too. The
  dispatcher reassigns `win_workman_task` on every loop iteration, which is why the guard
  is anchored there.

Roles that take a dependency accept `nodep` in the task string to skip it — the guard adds
a second condition:

```yaml
  when:
    - (win_workman_task.act | default('on', true)) == 'on'
    - "'nodep' not in (win_workman_task_argv | default([]))"
```

The `# win_workman_dep: <fqcn>` comment above each block is the marker the catalog docs are
generated from — keep it in sync.

Current dependency edges: `winfsp` → `virtiogt`; `mysql_server`, `mysql_workbench`, `ntop`,
`seb`, `sketchup2026` → `vcredist14`; `gcpw`, `googledrive` → `chrome`.

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
