---
name: win-edulab-mcp
description: Use when operating the win-edulab MCP server — running tasks or playbooks on lab hosts, running one-off PowerShell through run_powershell, discovering inventory, querying role capabilities, and composing multi-role operations via run_tasks or run_playbook.
---

# win-edulab MCP — Operational Guide

## Available tools

### win-edulab server

| Tool | When to use |
|------|-------------|
| `get_inventory` | Before any operation: discover hosts, groups, IP and MAC addresses |
| `run_playbook` | Standalone playbooks (veyon, seb_classroom, wol) |
| `run_powershell` | One-off PowerShell on Windows hosts: diagnosis, inspection, a fix with no role behind it |
| `run_status` | Read a run started with `background=true` without waiting for it |
| `wait_run` | Block until a background run ends and return its output — only when the next step depends on the result (see **Long runs**) |

### win-workman server

| Tool | When to use |
|------|-------------|
| `get_role_info` | When the role has custom actions or configurable defaults; returns display_name, custom_actions, defaults, notes, and for package roles `install_scopes` (`sys`/`usr`) plus `usr_actions` for per-user roles |
| `run_tasks` | Install/remove software, run operations on hosts/groups via the `lineadicomando.win_workman.win_workman` FQCN playbook |
| `run_status`, `wait_run` | Same as on the win-edulab server, for runs started by `run_tasks` |

### samba-dc server

| Tool | When to use |
|------|-------------|
| `samba_dc_build` | Build (or bring back the configuration of) the Samba AD DC |
| `samba_dc_backup` | DC backup and restore |

### addcctl server (on the DC)

| Tool | When to use |
|------|-------------|
| `user_*`, `group_*`, `computer_*` | Domain accounts: list, get, create, change, delete |
| `home_provision`, `home_delete` | Users' home directories (H:) |
| `share_*` | Shared folders and their drive mapping |
| `domain_password_policy` | The password and lockout settings |

---

## Standard workflow

```
1. get_inventory (inventory=<lab>)   → discover available hosts and groups
2. get_role_info <role>              → only if the role has non-standard actions/defaults
3. run_tasks (preview=true)          → show the command, ask the user for confirmation
4. run_tasks                         → execute
```

**Rule**: always use `preview=true` before destructive operations (`-off`, `shutdown`, `logoff`, `lock`) or operations that require extra variables.

**Inventory**: the default is `school`. For any other lab always pass `inventory=<name>` (e.g. `ario_info`, `ario_ling`, `spalla_info1`, `spalla_info2`, `spalla_ling`, `spalla_aule`) to both `get_inventory` and `run_tasks`/`run_playbook`.

---

## Long runs: keep the chat free

Anything longer than a few seconds — a package install, a whole-lab run, a pkg lifecycle
test — runs with `background=true` **and** is then awaited from outside the turn, so the
user can keep typing while it works.

```
1. run_tasks(..., background=true)          → returns the run id and its log path
2. Bash, run_in_background:
     until [ -f logs/<run>.log.done ]; do sleep 10; done
3. the harness re-invokes on exit           → read the log, report the outcome
```

Every run writes `logs/<run>.log.done` once the log is flushed; the sentinel holds the
exit code. That file is the only reliable signal — **never** wait on a `pgrep -f` of the
ansible command line, because the watcher shell matches its own command line and the
loop never exits.

A background run is supervised by a detached process, not by the MCP server: it
survives a server restart or the end of the chat session and still writes its log
marker and sentinel. After such a restart, pick it up again from the sentinel.

**`wait_run` blocks the turn.** Calling it straight after starting a background run is
the same as running synchronously: `background=true` buys nothing and the chat stays
busy until the run ends. Use it only when the very next action depends on the result and
nothing else can usefully happen meanwhile. `run_status` reads a run *without* waiting.

**A whole lab runs five hosts at a time unless told otherwise.** `run_tasks`,
`run_playbook` and `run_powershell` take `forks`, passed as `-f`: set it to the number of
hosts when the run is long on each one (a Windows Update, a large install), e.g.
`run_tasks(t=["wu-run"], inventory="spalla_info2", forks=29, background=true)`. Omitted,
Ansible's configured value applies, 5 by default.


---

## run_powershell — one-off PowerShell

Runs a script through `ansible.windows.win_powershell`, inheriting the inventory's
addresses, vault credentials and SSH arguments. **Never** drop to `ansible -m win_shell`
in a terminal instead: the MCP call is what puts the run in `logs/` and redacts its
secrets.

### When to use it, and when not to

| Situation | Tool |
|-----------|------|
| "Is the Veyon service running on PC07?" | `run_powershell` |
| "Why did the Chrome install fail here?" | `run_powershell` |
| Anything the catalog already covers | `run_tasks` |
| A sequence worth repeating, or one needing idempotency | a playbook in `local/`, or a new role |

A script that gets written twice is a role that is missing. See **win-workman-new-role**.

### What comes back

Objects, not console text. Either leave them on the success stream, or set
`$Ansible.Result` to say exactly what the answer is:

```json
{ "script": "$Ansible.Result = @{ Version = (Get-Item 'C:\\Program Files\\Veyon\\veyon-master.exe').VersionInfo.FileVersion }", "l": "teacher" }
```

Other `$Ansible` members: `Changed`, `Failed`, `Tmpdir`, `Diff`.

### The rules that save a round trip

- **Windows PowerShell 5.1**, not pwsh 7: no ternary operator, no
  `ConvertFrom-Json -AsHashtable`, no `Get-Error`.
- **Project with `Select-Object`** before returning: a bare `Get-Process` serialises
  megabytes and gets truncated. `depth` defaults to 3; raising it grows output fast.
- **Values go in `parameters`**, into a `param()` block — not built into the script text.
  No quoting, no injection.
- **Secrets go in `sensitive_parameters`** (`{name, value}` or `{name, username,
  password}`): passed as SecureString/PSCredential and kept out of the log.
- `read_only` defaults to true and appends `$Ansible.Changed = $false`. Set it to
  **false** for a script that modifies the host, or the run reports a lie.
- `error_action` defaults to `stop`: an error record fails the task instead of
  passing unnoticed.
- `l` is **required** and has no default. More than 3 hosts needs `confirm=true`.
- Windows hosts only; the Linux DC is the job of the samba-dc and addcctl servers.

### Examples

```json
{ "script": "Get-Service -Name Veyon* | Select-Object Name, Status, StartType", "l": "teacher" }
```

```json
{ "script": "param([String]$Path)\nGet-ChildItem $Path | Select-Object -First 5 Name, Length",
  "l": "students", "parameters": { "Path": "C:\\Windows\\Temp" }, "confirm": true }
```

```json
{ "script": "Restart-Service -Name VeyonService", "l": "PC07", "read_only": false }
```

Hosts that answer alike are folded into one entry, so a whole lab reads as a few lines
rather than one JSON blob per PC.

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

`run_tasks` takes role variables in `extra_vars` (an object, passed as Ansible extra vars);
`t` and `ansible_*` keys are refused. Prefer the task string (action + positional argument)
when the role offers one, e.g. `zed-usr-on-student-alice+student-bob` rather than
`extra_vars: {"win_workman_usr_targets": [...]}`.

`l` defaults to `win_managed`, the managed Windows PCs (`lab_win` where an inventory still
has only the old name); `all` also reaches the domain
controller and has to be asked for explicitly.

Secrets — a password, a licence code — never go in `extra_vars` or in the `e` of
`run_playbook`: pass them in `sensitive_vars`, an object of the same shape that both
tools merge with the other variables. They reach Ansible through a private file instead
of the command line and are masked in the log, in the output and in a preview:

```json
{ "t": ["autologon-on"], "l": "students",
  "extra_vars": { "win_workman_autologon_username": "studente" },
  "sensitive_vars": { "win_workman_autologon_password": "..." } }
```

The samba-dc tools do the same on their own for `args.administrator_passwd` and
`args.domain_password`; the addcctl tools never put a password on a command line.

**run_playbook** — for standalone playbooks with their own logic:

| Playbook | Default target | Accepts `target_hosts` | Use |
|----------|---------------|------------------------|-----|
| `veyon` | `win_managed` | yes | Full Veyon setup: keypair generation, config deploy, network objects |
| `seb_classroom` | `students` | yes | SEB configuration for an entire classroom |
| `wol` | `win_managed` | yes | Wake-on-LAN broadcast across the inventory |
| `lab_cad` | `lab_cad` | yes | CAD lab software setup |
| `lab_coding` | `lab_coding` | yes | Coding lab software setup |
| `maintenance` | `win_managed` | yes | System maintenance: wol (skipped on hosts with no `ansible_mac`) → lock → restart-if-pending → chkdsk → wim-scan → sfc → optimize, then unlock → restart even on failure (no Windows Update) |
| `samba_dc_join` | `win_managed` | yes | Join Windows hosts to the Samba AD domain |
| `samba_dc_build` | `samba_dc` | yes | Build a new Samba AD Domain Controller |
| `gcpw` | `win_managed` | yes | Google Credential Provider for Windows |
| `shutdown` | `win_managed` | yes | Shut the lab down |

Pass `target_hosts` via the `e` parameter to override the default group:

```json
{ "playbook": "veyon", "e": { "target_hosts": "teacher" } }
{ "playbook": "seb_classroom", "e": { "target_hosts": "student01" } }
{ "playbook": "wol", "e": { "target_hosts": "lab_cad" } }
```

> **Note on autologon**: use `run_tasks(["autologon-on"])` to enable autologon with role defaults. The `autologon.yaml` standalone playbook is a fixed shortcut that hardcodes `win_workman_autologon_restart: true` and targets `win_managed` — prefer `run_tasks` unless that exact behaviour is needed.

---

## Typical inventory groups

Discovered via `get_inventory`; groups common to most inventories:
- `teachers` — teacher PC(s)
- `students` — student PCs
- `win_managed` — all managed Windows PCs, in labs or not (built from the lab groups, or from teachers + students); carries the connection settings
- `servers` — Linux servers (dc01 etc.)
- `samba_dc` — domain controller(s); **required by the samba_dc collection** — all inventories that use the samba tools must define this group

---

## Samba AD DC operations

Two servers: **samba-dc** (`samba_dc_build`, `samba_dc_backup`: playbooks, target
`samba_dc` by default) and **addcctl** (`addcctl mcp` on the DC, through SSH: users,
groups, computers, home directories, shared folders). There is no `samba` tool any
more (collection v0.9.0); OUs have no tool yet.

### Standard workflow (addcctl)
```
1. user_list / group_list / share_list   → look before changing
2. <tool> with "check": true             → what it would change, nothing changed
3. <tool>                                → execute, after the user confirms
```

**Rule**: always `"check": true` first for destructive calls (`user_delete`,
`group_delete`, `computer_delete`, `home_delete`, `share_delete`, a `share_set` or
`group_set` that removes entries) and confirm with the user.

### addcctl — tools

| Object | Tools |
|--------|-------|
| user | `user_list`, `user_get`, `user_create`, `user_set`, `user_password`, `user_unlock`, `user_delete` |
| group | `group_list`, `group_get`, `group_create`, `group_set`, `group_delete` |
| computer | `computer_list`, `computer_get`, `computer_create`, `computer_delete` |
| home | `home_provision`, `home_delete` |
| share | `share_list`, `share_get`, `share_set`, `share_delete`, `share_rename_principal` |
| domain | `domain_password_policy` |

The input of each tool is in its schema (the MCP client shows it): names are
sAMAccountNames; `user_set` and `group_set` change only what they are given and take
`groups`/`members` with a `*_mode` of `replace` (default), `append` or `remove`;
`new_name` renames the account and its entries in the shared folders.

**home_provision** creates `/srv/samba/home/<user>`, sets `homeDrive` (default `H:`)
and `homeDirectory`, and makes sure the hidden `home` share serves it.
`home_delete` clears the attributes; with `delete_data: true` it also removes the
folder (destructive).

**share_set** is the **Shared folders** tab of cockpit-samba-dc: whatever is created
here shows up in Cockpit and vice versa. Folder `/srv/samba/shares/<name>`, access
`[{name, kind, level}]` (`level` `read` by default or `write`; `kind` looked up when
omitted) with `access_mode` `replace`/`append`/`remove`, `comment`, `browseable`,
`drive` `{letter, label}` (E–Z except H; `null` removes the mapping) through the
**Cockpit - Mapped drives** GPO. A share always keeps at least one entry. Registry
shares outside `/srv/samba/shares` (such as `home`) are never touched. `share_delete`
keeps the folder unless `delete_data: true`.

Passwords (`user_create`, `user_password`) reach `addcctl` on stdin and are never
returned or logged.

```json
user_create      { "name": "alice", "password": "...", "groups": ["Students"], "check": true }
group_set        { "name": "staff", "members": ["alice", "bob"], "members_mode": "append" }
home_provision   { "name": "alice" }
home_delete      { "name": "alice", "delete_data": true, "check": true }
share_set        { "name": "Materiali", "access": [{ "name": "Teachers", "level": "write" }, { "name": "Students" }], "drive": { "letter": "M" } }
share_set        { "name": "Materiali", "access": [{ "name": "Students" }], "access_mode": "remove", "check": true }
share_delete     { "name": "Materiali", "delete_data": true, "check": true }
```

### samba_dc_build — build a DC

`args`: role variables without the `samba_dc_build_` prefix, over the inventory's.
It changes the system and may reboot it: `preview` first, then confirm.
`force_provision: true` destroys the domain and needs `force_provision_confirm: true`.

### samba_dc_backup — backup and restore

Backup args: `targetdir` (required), `domain` (bool, default true), `domain_type` (`online`|`offline`, default `offline`), `files` (bool, default true), `files_paths` (list, default `[/home, /srv/samba]`).

Restore args: `restore_backup_file`, `restore_targetdir`, `restore_newservername`, `restore_confirm=true` (all required).

```json
{ "action": "backup", "args": { "targetdir": "/var/backups/samba" } }
{ "action": "backup", "args": { "targetdir": "/var/backups/samba", "files_paths": ["/home", "/srv/samba"] } }
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

### Per-user install (deferred to logon) for a group, minus one user
```json
{ "t": ["zed-usr-on-Students", "zed-usr-off-student-bob"], "l": "lab_coding", "preview": true }
```
Then `zed-usr-apply` for users already logged on, `zed-usr-info` to see who has it.

### Per-user install targets with spaces, via extra_vars
```json
{ "t": ["zed-usr-on"], "l": "teacher", "extra_vars": { "win_workman_usr_targets": ["Domain Users"] }, "preview": true }
```

### Enable autologon with role defaults
```json
{ "t": ["autologon-on"], "l": "students", "preview": true }
```

### Lock down a lab during maintenance
```json
{ "t": ["lock-on"], "l": "win_managed", "preview": true }
```

### Pause Windows Update for 7 days (role default)
```json
{ "t": ["wu-pause"], "l": "win_managed", "preview": true }
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
{ "t": ["wu-max_pause_days-90"], "l": "win_managed", "preview": true }
```

### Routine lab maintenance
```json
{ "playbook": "maintenance", "inventory": "ario_info", "background": true }
```
`run_playbook` has no `preview`: this call runs. Confirm with the user first.

Runs in sequence: wol, lock (which logs users off), restart-if-pending, chkdsk, wim-scan, sfc, optimize, then unlock and restart. A host that fails a check skips the ones after it and is reported failed, but is still unlocked and restarted. It does not run Windows Update: use `wu-run` (security) or `wu-run-full` through `run_tasks`.

### See what Windows Update offers, then install an optional feature update
```json
{ "t": ["wu-scan"], "l": "win_managed", "inventory": "ario_info" }
{ "t": ["wu-run-optional-upgrades", "wu-run"], "l": "win_managed", "inventory": "ario_info", "preview": true }
```
`wu-run-upgrades` finds nothing when the feature update is offered as optional (26H2 on 25H2 hosts): `wu-scan` lists it under "Optional", and `wu-run-optional-<category>` installs it. The `wu-run` after it brings the cumulative of the new release.

### Windows Update pause expressed in weeks
```json
{ "t": ["wu-pause-3-w"], "l": "students", "preview": true }
```
`wu-pause-<n>-<u>`: valid units `d` (days), `w` (weeks), `m` (months). `wu-pause-3-w` = 21 days.

### Home provisioning for a new AD user
```json
home_provision { "name": "alice" }
```
Creates `/srv/samba/home/alice`, sets `homeDrive: H:` and `homeDirectory: \\DC\home\alice` in the directory, and makes sure the SMB share `home` serves it.

### Removing a user's home directory (with confirmation)
```json
home_delete { "name": "alice", "delete_data": true, "check": true }
```
