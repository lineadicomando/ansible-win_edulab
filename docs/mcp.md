# MCP Server — win-edulab

The `mcp/` directory contains an MCP (Model Context Protocol) server that exposes
the collection to Claude Code. It lets you manage lab workstations in natural language:
"install Chrome on teacher", "run chkdsk on all students", and so on.

## Architecture

```
Claude Code
    │  MCP (stdio)
    ▼
mcp/server.py          ← MCP server: get_inventory, run_playbook, run_powershell, run_status
    ├── ansible_runner.py   ← builds and runs ansible-playbook subprocesses
    ├── adhoc.py            ← builds ad-hoc win_powershell runs, renders their results
    ├── preflight.py        ← checks inventory, vault and SSH keys before a run
    ├── runlog.py           ← streams each run to a log file under logs/
    └── inventory.py        ← parses hosts.yaml files, lists available roles
         │
         ▼
ansible-playbook ...   ← runs against the real managed hosts
```

The server communicates over **stdio** (stdin/stdout). Claude Code launches it as a
subprocess when the session starts and sends JSON-RPC messages over the pipe.

---

## Installation

The MCP server requires the `mcp` and `pyyaml` Python packages. They are declared in
`mcp/pyproject.toml` and must be installed in the Python interpreter that Claude Code
will invoke.

### Option A — virtual environment (recommended)

A dedicated venv keeps the dependencies isolated and avoids conflicts with
system packages. Install once, then point `.mcp.json` at the venv interpreter.

```bash
cd /path/to/ansible-collection-win_edulab
python3 -m venv mcp/.venv
mcp/.venv/bin/pip install -e mcp/
```

Then update `.mcp.json` to use the venv interpreter (absolute path required):

```json
{
  "mcpServers": {
    "win-edulab": {
      "command": "/path/to/ansible-collection-win_edulab/mcp/.venv/bin/python3",
      "args": ["/path/to/ansible-collection-win_edulab/mcp/server.py"]
    }
  }
}
```

### Option B — user-level install

If you prefer to install globally for the current user:

```bash
pip install --user mcp pyyaml
```

Keep `.mcp.json` as-is (`"command": "python3"`). This works as long as `~/.local/bin`
is on `PATH` and the user-site packages are visible to the system `python3`.

### Verifying the install

```bash
/path/to/mcp/.venv/bin/python3 -c "import mcp, yaml; print('OK')"
```

---

## Configuration files

### `.mcp.json` (project root)

Declares the server to Claude Code. Committed to the repository so every developer
gets the server automatically.

```json
{
  "mcpServers": {
    "win-edulab": {
      "command": "python3",
      "args": ["./mcp/server.py"]
    }
  }
}
```

`args` can use paths relative to the project root. Claude Code sets the working
directory to the project root before launching the server.

### `.claude/settings.json`

Contains `"enableAllProjectMcpServers": true`, which tells Claude Code to load
the server from `.mcp.json` without prompting for approval on every session start.
This file is already committed to the repository.

### Restart

After editing `.mcp.json` or installing dependencies, restart Claude Code (or the
current session) for the changes to take effect.

---

## Available tools

### `get_inventory`

Returns all hosts and groups from an inventory, with their IP and MAC addresses.
Call this first when you need to discover which hosts or groups are available.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inventory` | string | `school` | Inventory name under `inventories/` |

**Available inventories:** `ario_info`, `ario_ling`, `school`, `spalla_info1`,
`spalla_info2`, `spalla_ling`, `test`

**Example response:**

```json
{
  "hosts": {
    "teacher":    { "ansible_host": "172.16.2.10" },
    "student01":  { "ansible_host": "172.16.2.11" },
    "student02":  { "ansible_host": "172.16.2.12" },
    "samba-ad-dc":{ "ansible_host": "172.16.0.3"  }
  },
  "groups": {
    "teachers":  ["teacher"],
    "students":  ["student01", "student02"],
    "servers":   ["samba-ad-dc"],
    "windows11": ["teacher", "student01", "student02"]
  }
}
```

---

### `run_tasks`

Runs one or more `win_workman` tasks on a host or group via `playbooks/win_wm.yaml`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `t` | string[] | yes | — | Task list, e.g. `["chrome"]` or `["chkdsk", "sfc"]` |
| `l` | string | no | `all` | Ansible limit: hostname or group name |
| `inventory` | string | no | `school` | Inventory name under `inventories/` |
| `preview` | boolean | no | `false` | Return the command without executing it |

#### Task format

```
<role>[-<action>]
```

The action is optional; omitting it defaults to `on` (install/enable).

| Action | Effect |
|--------|--------|
| `on` | Install / enable (default) |
| `off` | Uninstall / disable |
| `info` | Report current state; never changes anything |
| `download` | Download installer to controller cache only |
| `copy` | Copy installer to remote temp dir; do not install |
| `is_present` | Fail the play if the software is not installed |

Examples: `chrome`, `chrome-off`, `chrome-info`, `chkdsk`, `sfc`, `wim-check`.

#### Available roles

Roles are read dynamically from `ansible_collections/lineadicomando/win_workman/roles/`
at server startup, so the list reflects whatever version of the collection is installed.
Typical roles include: `chrome`, `firefox`, `edge`, `brave`, `libreoffice`, `gimp`,
`inkscape`, `vscode`, `python310`–`python314`, `zoom`, `vlc`, `veyon`, `7zip`,
`chkdsk`, `sfc`, `wim`, `wu`, `restart`, `shutdown`, `wol`, `secure_ssh`, …

#### The `preview` flag

Set `preview: true` to get the exact `ansible-playbook` command that would run,
without executing it. Use this to show the user what will happen before confirming.

```
Tool call:  run_tasks(t=["chrome"], l="teacher", preview=true)

Response:
  Command to run:

    ansible-playbook \
      -i 'inventories/school/hosts.yaml' \
      -l 'teacher' \
      playbooks/win_wm.yaml \
      -e '{"t": "chrome"}'

  No command executed.
```

#### Multiple tasks

Pass multiple tasks in a single call to run them sequentially:

```json
{ "t": ["chkdsk", "sfc", "wim-check"], "l": "teacher" }
```

This translates to:

```bash
ansible-playbook -i inventories/school/hosts.yaml \
  -l teacher playbooks/win_wm.yaml \
  -e '{"t": "chkdsk,sfc,wim-check"}'
```

---

### `run_playbook`

Runs a standalone playbook from the `playbooks/` directory.
Use for playbooks that have their own logic and are not dispatched through
the `win_workman` role (e.g. `veyon`, `wol`, `seb_classroom`, `autologon`).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `playbook` | string | yes | — | Playbook name without `.yaml` extension |
| `l` | string | no | `all` | Ansible limit |
| `e` | object | no | `{}` | Extra vars passed as `-e '{...}'` |
| `inventory` | string | no | `school` | Inventory name |

**Available playbooks:** `autologon`, `cad`, `coding`, `seb_classroom`, `veyon`,
`win_wm`, `wol`

---

### `run_powershell`

Runs a PowerShell script on Windows hosts through `ansible.windows.win_powershell`,
using the inventory's addresses, vault credentials and SSH arguments. This is the
supported way to run a one-off command on a lab PC: it keeps the run in `logs/` and
keeps its secrets out of them, which a hand-typed `ansible -m win_shell` does not.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `script` | string | yes | — | The PowerShell script |
| `l` | string | yes | — | Host, group or comma-separated pattern; no default by design |
| `parameters` | object | no | `{}` | Values for the script's `param()` block, passed typed |
| `sensitive_parameters` | array | no | `[]` | `{name, value}` or `{name, username, password}`, passed as SecureString/PSCredential and redacted from the log |
| `read_only` | bool | no | `true` | Appends `$Ansible.Changed = $false` so a query is not reported as a change |
| `depth` | int | no | `3` | Serialisation depth of returned objects |
| `error_action` | string | no | `stop` | `$ErrorActionPreference`: `stop`, `continue`, `silently_continue` |
| `chdir` | string | no | — | PowerShell location to set first |
| `confirm` | bool | no | `false` | Required when the pattern selects more than 3 hosts |
| `inventory` | string | no | `school` | Inventory name |
| `timeout` | int | no | `300` | Seconds before the run is killed |
| `background` | bool | no | `false` | Return a run id instead of waiting; follow with `run_status` |

Why this module rather than `win_shell`: it returns **objects**, not console text. The
script can set `$Ansible.Result` to state its answer exactly, `$Ansible.Changed` to
report honestly whether it changed anything, and error records come back with their
exception details instead of being guessed from an exit code.

```json
{ "script": "Get-Service -Name Veyon* | Select-Object Name, Status", "l": "teacher" }
{ "script": "param([String]$Path)\nTest-Path $Path", "l": "students",
  "parameters": { "Path": "C:\\Program Files\\Veyon" }, "confirm": true }
```

Two constraints worth knowing before writing a script:

- it runs in **Windows PowerShell 5.1**, not pwsh 7 — no ternary operator, no
  `ConvertFrom-Json -AsHashtable`, no `Get-Error`;
- serialised objects are open-ended in size, so project them with `Select-Object`.
  Output past 4 KB per host, or 24 KB in total, is truncated with a note.

Results from hosts that answered identically are folded into a single entry, so a lab
of 25 PCs reads as a few lines instead of 25 JSON blobs.

Before running, the tool checks the inventory exists, that its vault is initialised and
its vault password file present, and that the SSH keys its `group_vars` reference are
readable — and refuses with that list rather than letting it surface as a connection
error per host.

---

### `samba`

Manages the Samba AD Domain Controller via `samba-tool`, through the
`lineadicomando.samba_ad_dc.samba` playbook. Requires the `samba_ad_dc`
collection installed in the Ansible environment and the DC present in the
inventory; `l` should target a single DC.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `object` | string | yes | — | `user`, `group`, `computer`, `ou`, `backup`, `restore` |
| `action` | string | no | — | samba-tool verb; not required for backup/restore |
| `args` | object | no | `{}` | Action-specific arguments |
| `l` | string | no | `all` | Ansible limit (the DC host or group) |
| `inventory` | string | no | `school` | Inventory name |
| `preview` | boolean | no | `false` | Return the command without executing it |

Common actions per object:

| Object | Actions |
|--------|---------|
| `user` | `list`, `show`, `create`, `delete`, `enable`, `disable`, `setpassword` |
| `group` | `list`, `show`, `listmembers`, `add`, `delete`, `addmembers`, `removemembers` |
| `computer` | `list`, `show`, `create`, `delete` |
| `ou` | `list`, `listobjects`, `create`, `delete` |
| `backup` | args `type` (`online`/`offline`), `targetdir` |
| `restore` | args `backup_file`, `targetdir`, `newservername`, `confirm: true` |

Read-only actions (`list`, `show`, `listmembers`, `listobjects`) never change
state. Use `preview: true` for destructive actions (`delete`, `disable`,
`removemembers`, `restore`) and confirm with the user before executing.

```
Tool call: samba(object="user", action="create",
                 args={"name": "alice", "password": "..."},
                 l="samba-ad-dc", preview=true)

Response:
  Command to run:

    ansible-playbook \
      lineadicomando.samba_ad_dc.samba \
      -i 'inventories/school/hosts.yaml' \
      -l 'samba-ad-dc' \
      -e '{"samba_tool_object": "user", "samba_tool_action": "create", ...}'

  No command executed.
```

---

## Confirmation pattern

For destructive or slow operations (uninstalls, reboots, mass targets), use `preview`
first and ask the user to confirm before executing.

```
User:   shut down all students
Agent:  Command to run:

          ansible-playbook -i 'inventories/school/hosts.yaml' \
            -l 'students' playbooks/win_wm.yaml \
            -e '{"t": "shutdown"}'

        Proceed?
User:   yes
Agent:  [runs — PLAY RECAP: student01 ok=3 changed=1 ...]
```

This pattern is especially important when `l` is a group name (affects multiple
hosts) or when the action is `off`, `shutdown`, or `restart`.

---

## Run logs

Every tool call that runs `ansible-playbook` streams its output to a log file under
`logs/` **while the playbook is still running**, so you can watch it progress instead
of waiting for the tool call to return. The directory is gitignored.

```
logs/
├── 20260910-095603-veyon-lab_ario_info.log
├── 20260910-100112-win_wm-chrome-teacher.log
└── latest.log -> 20260910-100112-win_wm-chrome-teacher.log
```

Leave a terminal open on the symlink and you see whatever starts next, from any of the
three MCP servers:

```bash
tail -F logs/latest.log
```

`-F` rather than `-f`: it follows the file *by name*, so it picks up the next run when
`latest.log` is repointed.

File names are `<timestamp>-<label>.log`, where the label identifies the call
(`veyon-lab_ario_info`, `win_wm-chrome_info-teacher`, `samba-user-list-dc`). The first
line of each log is the exact command that ran, the last is its exit code. The path is
also appended to the tool result as `[log] …`, so the agent can point you at it.

Only the newest 50 logs are kept; older ones are dropped as new runs start.
Set `ANSIBLE_MCP_LOG_DIR` to write them somewhere else.

### Why the output streams

Ansible does not flush its own stdout — it leaves that to the system and flushes at
shutdown — so over a pipe its output would only arrive in blocks. The runners launch it
with `PYTHONUNBUFFERED=1`, which restores line-by-line output. They also give the
playbook `stdin=DEVNULL`: the MCP server's own stdin is the JSON-RPC stream, and must
never be handed to a playbook that decides to prompt.

---

## Troubleshooting

### Server does not load / tools not available

1. Check that dependencies are installed in the correct Python interpreter:
   ```bash
   python3 -c "import mcp, yaml; print('OK')"
   ```
2. Check the server starts without errors:
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
     | python3 mcp/server.py
   ```
   You should receive a JSON response, not a traceback.
3. Verify `.claude/settings.json` contains `"enableAllProjectMcpServers": true`.
4. Restart the Claude Code session after any change to `.mcp.json`.

### `ModuleNotFoundError: No module named 'mcp'`

The `mcp` package is not installed in the Python interpreter that Claude Code is
invoking. Install it or switch `.mcp.json` to point at a venv (see
[Installation](#installation)).

### `ImportError: cannot import name 'Server' from partially initialized module 'mcp.server'`

Python is resolving `mcp.server` to the local file `mcp/server.py` instead of the
installed `mcp` package. This happens when `python3` is run from inside the `mcp/`
directory. Claude Code runs the server from the project root, so this should not
occur in normal use; it only appears when testing manually from inside `mcp/`.

To test manually from the project root:

```bash
python3 mcp/server.py
```

### Ansible command not found

`ansible-playbook` must be on the `PATH` of the shell environment in which Claude
Code is running. If you use a virtual environment for Ansible, activate it in your
shell before launching Claude Code, or set the full path in `ansible.cfg`.

### Relative path in args does not resolve

If `.mcp.json` uses a relative `args` path and the server fails to find `server.py`,
switch to an absolute path:

```json
{
  "mcpServers": {
    "win-edulab": {
      "command": "python3",
      "args": ["/absolute/path/to/ansible-collection-win_edulab/mcp/server.py"]
    }
  }
}
```

---

## Source layout

```
mcp/
├── server.py           # MCP entry point — declares and dispatches the tools
├── ansible_runner.py   # Builds ansible-playbook command lists, runs subprocesses
├── adhoc.py            # Ad-hoc win_powershell command lines, host counting, result rendering
├── preflight.py        # Inventory, vault and SSH key checks run before a command
├── inventory.py        # Parses hosts.yaml, lists inventories and installed roles
├── runlog.py           # Per-run log files under logs/, written while the playbook runs
└── pyproject.toml      # Package metadata and dependencies (mcp>=1.0, pyyaml>=6.0)
```

### `ansible_runner.py`

- `build_playbook_command(playbook, l, e, inventory)` — builds a playbook command list
- `run_command(cmd, label)` — runs the command, tees its output to `logs/` line by line,
  returns the combined stdout/stderr plus the log path
- `run_raw(cmd, label, notify, timeout, env, redact)` — the same, returning the
  `RunResult` for a caller that renders the output itself

The `run_tasks` and `samba` tools documented above belong to the `win-workman` and
`samba-ad-dc` MCP servers, which live in their own collections and keep their own
command builders.

### `runlog.py`

- `run_logged(cmd, root, label, timeout=None)` — runs a command with its output written
  to `logs/<timestamp>-<label>.log` as it arrives, and `logs/latest.log` repointed at it;
  returns `(output, returncode, log_path, timed_out)`

### `adhoc.py`

- `build_powershell_command(script, l, inventory, ...)` — an `ansible -m win_powershell`
  command list; module arguments are passed as JSON, so a script survives quotes, `$`
  and newlines intact, and a script containing Jinja delimiters is wrapped in
  `{% raw %}`
- `resolve_hosts(l, inventory)` — the hosts a pattern selects, for sizing a command
  before running it; exclusions are ignored, so the count errs high
- `secret_values(sensitive_parameters)` — the values the run must keep out of its log
- `summarise(text)` — folds ad-hoc output into per-host blocks, collapsing hosts that
  answered alike

### `preflight.py`

- `preflight(inventory)` — what is missing before a run can work: unknown inventory,
  absent `hosts.yaml`, an uninitialised vault, a missing vault password file, an SSH
  key referenced by `group_vars` that does not exist. An empty list means ready

### `inventory.py`

- `load_inventory(inventory)` — loads and parses a `hosts.yaml` into `{hosts, groups}`
- `list_inventories()` — returns sorted directory names under `inventories/`
- `list_roles()` — returns sorted role names from the installed `win_workman` collection,
  excluding internal roles (`dispatcher`, `pkg_utils`)
