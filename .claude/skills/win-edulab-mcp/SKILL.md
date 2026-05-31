---
name: win-edulab-mcp
description: Use when operating the win-edulab MCP server — running tasks or playbooks on lab hosts, discovering inventory, querying role capabilities, and composing multi-role operations via run_tasks or run_playbook.
---

# win-edulab MCP — Operational Guide

## Available tools

### win-edulab server

| Tool | When to use |
|------|-------------|
| `get_inventory` | Before any operation: discover hosts, groups, IP and MAC addresses |
| `run_playbook` | Standalone playbooks (veyon, seb_classroom, wol) |

### win-workman server

| Tool | When to use |
|------|-------------|
| `get_role_info` | When the role has custom actions or configurable defaults; returns display_name, custom_actions, defaults, notes |
| `run_tasks` | Install/remove software, run operations on hosts/groups via the `lineadicomando.win_workman.win_workman` FQCN playbook |

### samba-ad-dc server

| Tool | When to use |
|------|-------------|
| `samba` | AD object management (users, groups, computers, OUs) via samba-tool |
| `samba_dc_backup` | DC backup and restore |

---

## Standard workflow

```
1. get_inventory (inventory=<lab>)   → discover available hosts and groups
2. get_role_info <role>              → only if the role has non-standard actions/defaults
3. run_tasks (preview=true)          → show the command, ask the user for confirmation
4. run_tasks                         → execute
```

**Rule**: always use `preview=true` before destructive operations (`-off`, `shutdown`, `logoff`, `lock`) or operations that require extra variables.

**Inventory**: the default is `school`. For any other lab always pass `inventory=<name>` (e.g. `ario_info`, `ario_ling`, `spalla_info1`, `spalla_info2`, `spalla_ling`) to both `get_inventory` and `run_tasks`/`run_playbook`.

---

## Task string format

```
<role>                    → install (implicit 'on' action)
<role>-<action>           → explicit action
<role>-<action>-<arg>     → action with positional argument (dash-separated)
<role>-<action>-<n>-<u>  → action with numeric arg and unit (e.g. wu-pause-3-w)
```

Examples: `chrome`, `chrome-off`, `chrome-on-32bit`, `wu-pause-84`, `wallpaper-set`, `restart-if`

Arguments are **always dash-separated** — spaces are not supported by the parser.

See the **win-workman-task-syntax** skill for the full syntax and standard action list.

---

## When to call get_role_info

Call `get_role_info` before `run_tasks` when:
- The role has **custom actions** you don't know (e.g. `wu`, `wallpaper`, `seb`, `restart`)
- The role accepts configurable **extra_vars** (e.g. `chrome` with shortcuts, `autologon` with credentials, `lock` with custom text)
- The user asks "what does `<role>` do" or "what options does it have"

Not needed for standard roles without custom actions (e.g. `vlc`, `git`, `python313`).

---

## run_tasks vs run_playbook

**run_tasks** — for everything that goes through the `lineadicomando.win_workman.win_workman` FQCN playbook:
- Software install/remove
- System operations (restart, shutdown, logoff, wu, sfc, wim, chkdsk)
- Configuration (lock, autologon, wallpaper, ms_account, widgets, oobe)

`run_tasks` accepts **no extra vars** (`e` is not a supported parameter). Role behaviour is controlled only via the task string (action + positional argument).

**run_playbook** — for standalone playbooks with their own logic:

| Playbook | Default target | Accepts `target_hosts` | Use |
|----------|---------------|------------------------|-----|
| `veyon` | `lab_win` | yes | Full Veyon setup: keypair generation, config deploy, network objects |
| `seb_classroom` | `students` | yes | SEB configuration for an entire classroom |
| `wol` | `lab_win` | yes | Wake-on-LAN broadcast across the inventory |
| `lab_cad` | `lab_cad` | yes | CAD lab software setup |
| `lab_coding` | `lab_coding` | yes | Coding lab software setup |
| `maintenance` | `lab_win` | yes | Full maintenance cycle: lock → wu-run → wim/sfc → chrome/edge → wallpaper → wu-pause → restart → unlock |
| `samba_dc_join` | `lab_win` | yes | Join Windows hosts to the Samba AD domain |
| `samba_dc_build` | `samba_ad_dc` | yes | Build a new Samba AD Domain Controller |

Pass `target_hosts` via the `e` parameter to override the default group:

```json
{ "playbook": "veyon", "e": { "target_hosts": "teacher" } }
{ "playbook": "seb_classroom", "e": { "target_hosts": "student01" } }
{ "playbook": "wol", "e": { "target_hosts": "lab_cad" } }
```

> **Note on autologon**: use `run_tasks(["autologon-on"])` to enable autologon with role defaults. The `autologon.yaml` standalone playbook is a fixed shortcut that hardcodes `win_workman_autologon_restart: true` and targets `lab_win` — prefer `run_tasks` unless that exact behaviour is needed.

---

## Typical inventory groups

Discovered via `get_inventory`; groups common to most inventories:
- `teachers` — teacher PC(s)
- `students` — student PCs
- `lab_win` — all Windows PCs in the lab (teachers + students)
- `windows11` — all Windows 11 hosts
- `servers` — Linux servers (samba-ad-dc etc.)
- `samba_dc` — domain controller(s); **required by the samba_ad_dc collection** — all inventories that use the samba tools must define this group

---

## Samba AD DC operations

The `samba` and `samba_dc_backup` tools target `samba_dc` by default. Explicit `l` is only needed to override (e.g. multi-DC environments).

### Standard workflow
```
1. get_inventory            → verify samba_dc group and DC hostname
2. samba (preview=true)     → confirm command before any mutating action
3. samba                    → execute
```

**Rule**: always use `preview=true` before destructive actions (`delete`, `absent`, `disable`, `removemembers`, `home-absent`, restore).

### samba — object actions

| Object | Actions |
|--------|---------|
| `user` | `list`, `show`, `create`, `present`, `delete`, `absent`, `enable`, `disable`, `setpassword`, `setprimarygroup` |
| `group` | `list`, `show`, `listmembers`, `add`, `create`, `delete`, `absent`, `addmembers`, `removemembers` |
| `computer` | `list`, `show`, `create`, `delete`, `absent` |
| `ou` | `list`, `listobjects`, `create`, `delete`, `absent` |
| `home` | `provision`, `absent` |

`present`/`absent` are idempotent aliases: `present` = create-or-enable; `absent` = delete-or-skip-if-missing.

#### home — user directory provisioning

Replicates the cockpit-samba-ad-dc logic: creates the physical directory, sets the LDAP attributes `homeDrive`/`homeDirectory` via `ldbmodify`, and ensures the SMB share exists.

| Argument | Default | Notes |
|----------|---------|-------|
| `name` | — | **required** — sAMAccountName of the user |
| `home_base` | `/home/samba` | base path for home directories |
| `home_drive` | `H:` | Windows drive letter |
| `share_name` | `home` | SMB share name (created only if it does not exist) |

`absent` removes the physical directory and clears the LDAP attributes. It is **destructive** — always use `preview=true`.

Examples:
```json
{ "object": "user", "action": "list" }
{ "object": "user", "action": "create", "args": { "name": "alice", "password": "Secret123!" } }
{ "object": "user", "action": "present", "args": { "name": "alice", "password": "Secret123!" } }
{ "object": "group", "action": "addmembers", "args": { "name": "staff", "members": ["alice", "bob"] } }
{ "object": "home", "action": "provision", "args": { "name": "alice" } }
{ "object": "home", "action": "provision", "args": { "name": "alice", "home_base": "/home/samba", "home_drive": "H:", "share_name": "home" } }
{ "object": "home", "action": "absent", "args": { "name": "alice" }, "preview": true }
```

### samba_dc_backup — backup and restore

Backup args: `targetdir` (required), `domain` (bool, default true), `domain_type` (`online`|`offline`, default `offline`), `files` (bool, default true), `files_paths` (list, default `[/home]`).

Restore args: `restore_backup_file`, `restore_targetdir`, `restore_newservername`, `restore_confirm=true` (all required).

```json
{ "action": "backup", "args": { "targetdir": "/var/backups/samba" } }
{ "action": "backup", "args": { "targetdir": "/var/backups/samba", "files_paths": ["/home", "/srv/shares"] } }
{ "action": "restore", "args": { "restore_backup_file": "/var/backups/samba/samba-backup.tar.gz",
    "restore_targetdir": "/var/lib/samba", "restore_newservername": "dc1",
    "restore_confirm": true }, "preview": true }
```

---

## Operational examples

### Install software on all students
```json
{ "t": ["chrome", "vscode", "git"], "l": "students", "inventory": "ario_info", "preview": true }
```

### Remove browsers from a specific host
```json
{ "t": ["firefox-off", "chrome-off"], "l": "PC01", "inventory": "ario_info", "preview": true }
```

### Enable autologon with role defaults
```json
{ "t": ["autologon-on"], "l": "students", "preview": true }
```

### Lock down a lab during maintenance
```json
{ "t": ["lock-on"], "l": "lab_win", "preview": true }
```

### Pause Windows Update for 7 days (role default)
```json
{ "t": ["wu-pause"], "l": "all", "preview": true }
```

### Pause Windows Update for a specific number of days
```json
{ "t": ["wu-pause-84"], "l": "students", "inventory": "ario_info", "preview": true }
```

### Read the current max pause cap
```json
{ "t": ["wu-max_pause_days"], "l": "teachers", "preview": true }
```

### Set the max pause cap to 90 days
```json
{ "t": ["wu-max_pause_days-90"], "l": "all", "preview": true }
```

### Routine lab maintenance
```json
{ "playbook": "maintenance", "inventory": "ario_info", "preview": true }
```
Runs in sequence: lock, wu-run, wim, sfc, chrome/edge updates, wallpaper, wu-pause, restart, unlock.

### Windows Update pause expressed in weeks
```json
{ "t": ["wu-pause-3-w"], "l": "students", "preview": true }
```
`wu-pause-<n>-<u>`: valid units `d` (days), `w` (weeks), `m` (months). `wu-pause-3-w` = 21 days.

### Home provisioning for a new AD user
```json
{ "object": "home", "action": "provision", "args": { "name": "alice" } }
```
Creates `/home/samba/alice`, sets `homeDrive: H:` and `homeDirectory: \\DC\home\alice` in LDAP, and ensures the SMB share `home` exists.

### Removing a user's home directory (with confirmation)
```json
{ "object": "home", "action": "absent", "args": { "name": "alice" }, "preview": true }
```
