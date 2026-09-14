# EduLab Management

Ansible project for managing a didactic computer lab: a Samba 4 Active
Directory Domain Controller on Debian and Windows 11 workstations.

Three **MCP servers** (Model Context Protocol) expose lab operations to Claude
Code, enabling natural-language management of workstations directly from the AI
assistant. A set of **Claude Code skills** embedded in the project assists in
writing playbooks, roles, and configurations following project conventions —
both are first-class features of the project alongside the Ansible automation.

> **Status:** This project is in early development and currently has a
> demonstrative scope. Production use requires substantial adaptation and
> customization to match the specific infrastructure, security policies, and
> operational requirements of each environment.

## Architecture

```
ansible-win_edulab                       ← this project (inventory + playbooks + MCP server)
    requires ↓
    lineadicomando.win_workman           ← Windows software & system management (+ MCP server)
    lineadicomando.samba_ad_dc           ← Samba 4 AD DC provisioning on Debian (+ MCP server)
```

## Requirements

Control node:

- Ansible >= 2.20 (the win_workman roles declare `min_ansible_version: "2.20"`)
- Git
- Python >= 3.11, only for the MCP servers
- An SSH key for the managed hosts (see `inventories/school/group_vars/all/vars.yaml`)

Managed hosts:

- Windows 11 with the OpenSSH server enabled: Ansible connects over SSH with
  PowerShell as the remote shell (see `group_vars/windows11/vars.yaml`)
- Debian 13 for the domain controller
- A local `maint` account with administrative rights on every host

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/lineadicomando/ansible-win_edulab.git
cd ansible-win_edulab
```

### 2. Create the vault password file

`ansible.cfg` reads the vault password from `.ansible-vault-pass.txt` (gitignored):

```bash
$EDITOR .ansible-vault-pass.txt
chmod 600 .ansible-vault-pass.txt
```

### 3. Create and encrypt the vault file

```bash
cp inventories/school/group_vars/all/vault.yaml.example \
   inventories/school/group_vars/all/vault.yaml

# Edit vault.yaml with the real credentials, then encrypt it
ansible-vault encrypt inventories/school/group_vars/all/vault.yaml

# To edit the vault later
ansible-vault edit inventories/school/group_vars/all/vault.yaml
```

`vault.yaml` variables:

| Variable | Description |
|---|---|
| `ansible_vault_password` | SSH password for the `maint` user |
| `ansible_vault_become_password` | sudo password (usually the same) |
| `samba_dc_build_administrator_passwd` | Domain administrator password; must satisfy AD complexity rules (at least 7 characters) or `samba-tool` refuses it |

### 4. Install Ansible collections

```bash
ansible-galaxy collection install -r requirements.yaml -p .
```

Collections are installed from the `main` branch of their Git repositories into
`./ansible_collections/` (gitignored). See [Updating Collections](#updating-collections)
to pull newer versions later.

### 5. Customize the inventory

Edit `inventories/school/hosts.yaml` with the actual addresses of your lab hosts.
The group names matter: each playbook targets one of them by default.

```yaml
all:
  children:
    servers:
      hosts:
        samba_ad_dc:
          ansible_host: <DC-IP>
          ansible_mac: <DC-MAC>
    teachers:
      hosts:
        teacher:
          ansible_host: <teacher-IP>
          ansible_mac: <teacher-MAC>     # used by Wake-on-LAN
    students:
      hosts:
        student01:
          ansible_host: <student1-IP>
          ansible_mac: <student1-MAC>
        student02:
          ansible_host: <student2-IP>
          ansible_mac: <student2-MAC>
    lab_win:         # all lab workstations: default target of most playbooks
      hosts: { teacher:, student01:, student02: }
    lab_cad:         # default target of lab_cad.yaml
      hosts: { teacher:, student01:, student02: }
    lab_coding:      # default target of lab_coding.yaml
      hosts: { teacher:, student01:, student02: }
    windows11:       # SSH/PowerShell connection settings, maintenance.yaml target
      hosts: { teacher:, student01:, student02: }
    debian13:
      hosts: { samba_ad_dc: }
    samba_dc:        # required by the lineadicomando.samba_ad_dc collection
      hosts: { samba_ad_dc: }
```

Edit `inventories/school/group_vars/all/vars.yaml` to set the SSH key path and
any collection-level defaults (storage path, browser shortcut URL, SEB and GCPW
domains). The subnet and broadcast address used by Wake-on-LAN are set in
`group_vars/servers/vars.yaml` and `group_vars/windows11/vars.yaml`.

> **Security note:** the default `ansible_ssh_common_args` disables host key
> verification, which is acceptable only on an isolated lab network. The file
> contains the strict equivalent to use elsewhere.

Additional inventories can live next to `school` under `inventories/`; they are
gitignored, so site-specific labs stay out of the repository.

### 6. Configure the Samba DC parameters

Edit the `samba_dc_build_*` variables in `inventories/school/group_vars/all/vars.yaml`:

```yaml
samba_dc_build_realm: SCHOOL.INTERNAL        # Kerberos realm (uppercase)
samba_dc_build_domain: SCHOOL                # NetBIOS domain name
samba_dc_build_fqdn: dc.school.internal
samba_dc_build_search_domain: school.internal
samba_dc_build_nameserver: 127.0.0.1         # DC is its own DNS server
samba_dc_build_address: 192.168.122.2        # static IP of the DC
samba_dc_build_netmask: 255.255.255.0
samba_dc_build_gateway: 192.168.122.1
samba_dc_build_ifname: enp1s0                # network interface name
samba_dc_build_ntp_server: 192.168.122.1     # upstream NTP server
samba_dc_build_ntp_allow_network: 192.168.122.0/24
samba_dc_build_administrator_username: admin
```

The `samba_win_join_*` variables in the same file are derived from these, so the
domain join always matches the DC that was built.

## Available Playbooks

Playbooks that target a group accept `-e target_hosts=<group|host>` to override
the default target; `-l` narrows it further.

| Playbook | Default target |
|---|---|
| `samba_dc_build.yaml` | `samba_ad_dc` |
| `samba_dc_join.yaml` | `lab_win` |
| `win_wm.yaml` | `all` — always pass `-l` |
| `lab_cad.yaml` | `lab_cad` |
| `lab_coding.yaml` | `lab_coding` |
| `veyon.yaml` | `lab_win` |
| `maintenance.yaml` | `windows11` |
| `autologon.yaml` | `lab_win` |
| `wol.yaml` | `lab_win` |
| `shutdown.yaml` | `lab_win` |
| `gcpw.yaml` | `lab_win` |
| `seb_classroom.yaml` | `students` |

### `samba_dc_build.yaml` — Provision the Samba AD DC

Builds a full Samba 4 Active Directory Domain Controller on a Debian host:
network configuration, firewall (nftables), Kerberos, NTP (chrony), Cockpit.
The role is idempotent: reruns skip the `samba-tool domain provision` step.

```bash
ansible-playbook playbooks/samba_dc_build.yaml
```

### `samba_dc_join.yaml` — Join Windows hosts to the domain

Joins Windows 11 workstations to the Samba AD domain.

```bash
ansible-playbook playbooks/samba_dc_join.yaml
```

### `win_wm.yaml` — Windows software and system management

Installs, uninstalls, or manages software and settings on Windows 11
workstations. Pass tasks via the `-e t=` parameter.

This playbook imports `lineadicomando.win_workman.win_workman`, which runs on
`hosts: all` and ignores `target_hosts`: **always limit it with `-l`**, or it
will also try to run Windows tasks against the domain controller.

```bash
# Install Chrome and Python 3.14
ansible-playbook playbooks/win_wm.yaml -l lab_win -e "t=chrome,python314"

# Uninstall Firefox
ansible-playbook playbooks/win_wm.yaml -l lab_win -e "t=firefox-off"

# Windows Update, then restart
ansible-playbook playbooks/win_wm.yaml -l lab_win -e "t=wu-run,restart"

# Target a single host
ansible-playbook playbooks/win_wm.yaml -l teacher -e "t=chrome"
```

Task format: `<software>[-<action>]` — default action is `on` (install).
Common actions: `on`, `off`, `download`, `info`.

Available tasks include: `chrome`, `firefox`, `edge`, `brave`, `libreoffice`,
`gimp`, `inkscape`, `vscode`, `python310`–`python314`, `zoom`, `veyon`,
`wu-run`, `wu-pause`, `restart`, `shutdown`, `lock-on`, `lock-off`,
`wallpaper`, … — the full catalogue is the `roles/` directory of the
win_workman collection, or the `get_role_info` MCP tool.

### `lab_cad.yaml` — CAD lab packages

Installs the CAD lab software set: LibreOffice, Chrome, SketchUp 2026,
AutoCAD LT 2026, TinyCAD.

```bash
ansible-playbook playbooks/lab_cad.yaml
```

### `lab_coding.yaml` — Coding lab packages

Installs the coding lab software set: LibreOffice, Chrome, Edge, Firefox,
Brave, GIMP, Inkscape, ntop, 7-Zip, PureData, Postman, VS Code, Python 3.14,
Embarcadero Dev-C++.

```bash
ansible-playbook playbooks/lab_coding.yaml
```

### `veyon.yaml` — Veyon classroom management

Installs and configures Veyon on all lab workstations. Teachers are
configured as Veyon masters, students as clients (`win_workman_veyon_master`
in `group_vars/teachers` and `group_vars/students`).

```bash
ansible-playbook playbooks/veyon.yaml
```

### `maintenance.yaml` — Routine maintenance

Wakes the workstations, logs users off and locks the logon screen with a
maintenance notice, then runs CHKDSK, the WIM component store check, SFC and
disk optimization. A second play unlocks the workstations and restarts them.

```bash
ansible-playbook playbooks/maintenance.yaml
```

### `autologon.yaml` — Windows autologon

Configures Windows autologon on lab workstations and restarts them.

```bash
ansible-playbook playbooks/autologon.yaml
```

### `wol.yaml` — Wake on LAN

Sends a Wake-on-LAN magic packet to the target hosts, using their `ansible_mac`.

```bash
ansible-playbook playbooks/wol.yaml
```

### `shutdown.yaml` — Shut down workstations

```bash
ansible-playbook playbooks/shutdown.yaml
```

### `gcpw.yaml` — Google Credential Provider for Windows

Installs GCPW, so users can log on to the workstations with their Google
Workspace account. Set `win_workman_gcpw_domains_allowed_to_login` to the
allowed domain(s).

```bash
ansible-playbook playbooks/gcpw.yaml -e win_workman_gcpw_domains_allowed_to_login=school.edu
```

### `seb_classroom.yaml` — Safe Exam Browser for Google Classroom

Installs and deploys Safe Exam Browser pre-configured for Google Classroom,
with URL filtering that allows Google domains and blocks Gemini and NotebookLM.

```bash
ansible-playbook playbooks/seb_classroom.yaml
# Override the Google Workspace domain for the account chooser
ansible-playbook playbooks/seb_classroom.yaml -e win_workman_seb_account_chooser=school.edu
```

## MCP Servers (Claude Code integration)

Three MCP servers expose the project to Claude Code:

- **win-edulab** — this project's server, in `mcp/`
- **win-workman** — shipped with the `lineadicomando.win_workman` collection
- **samba-ad-dc** — shipped with the `lineadicomando.samba_ad_dc` collection

For full documentation see [`docs/mcp.md`](docs/mcp.md).

### 1. Install Python dependencies

```bash
pip install --user mcp pyyaml
```

Or use a virtual environment to keep the dependencies isolated:

```bash
python3 -m venv mcp/.venv
mcp/.venv/bin/pip install -e mcp/
# Then update the "command" entries in .mcp.json to point at mcp/.venv/bin/python3
```

### 2. Configure `.mcp.json`

`.mcp.json` is gitignored because it contains machine-specific absolute paths.
Copy the provided template and update the paths for your environment:

```bash
cp .mcp.json.example .mcp.json
# Edit .mcp.json with the actual paths on your machine
```

The collection servers can point either at a separate checkout of each
collection or at the copy installed by `ansible-galaxy`, e.g.
`ansible_collections/lineadicomando/win_workman/mcp/server.py`.
`ANSIBLE_PROJECT_ROOT` must point at this project.

Restart Claude Code after editing `.mcp.json` or installing dependencies.

### Available tools

**win-edulab**:

| Tool | Description |
|------|-------------|
| `get_inventory` | Returns hosts and groups with IPs for a given inventory |
| `run_playbook` | Runs a playbook from the `playbooks/` directory |
| `run_powershell` | Runs a one-off PowerShell script on Windows hosts, keeping secrets out of the run log |
| `run_status` | Reads the state and output of a run without waiting |
| `wait_run` | Waits for a background run to finish and returns its output |

**win-workman**:

| Tool | Description |
|------|-------------|
| `get_role_info` | Returns display name, available actions, and defaults for a win_workman role |
| `run_tasks` | Runs one or more win_workman tasks on lab hosts |
| `run_status` | Reads the state and output of a run without waiting |
| `wait_run` | Waits for a background run to finish and returns its output |

**samba-ad-dc**:

| Tool | Description |
|------|-------------|
| `samba` | Manages the domain controller through `samba-tool` |
| `samba_dc_backup` | Backs up and restores the domain controller |
| `samba_win_status` | Reports the domain or workgroup membership of Windows hosts |

Before running, `run_powershell` checks that the inventory exists and that its
vault and SSH key are in place, so a missing configuration is reported by name instead
of surfacing as a connection error on every host.

### Run logs

Every run is recorded under `logs/` (gitignored). Long operations can be started
with `background=true`: the run writes `logs/<run>.log` and creates
`logs/<run>.log.done` when it ends. To follow a run from a terminal:

```bash
bin/wmlog          # follow the most recent run until it ends
bin/wmlog -l       # list the ten most recent runs and their state
```

### Example interaction

```
User:    install VLC on teacher
Agent:   [run_tasks, preview] Command to run:
           ansible-playbook lineadicomando.win_workman.win_workman \
             -i inventories/school/hosts.yaml -l teacher -e '{"t": "vlc"}'
         Proceed?
User:    yes
Agent:   [run_tasks — PLAY RECAP: teacher ok=31 changed=1]
```

## Claude Code Skills

The skills in `.claude/skills/` are loaded by Claude Code when the task matches
them; `CLAUDE.md` holds the project directives the agent follows.

| Skill | Covers |
|---|---|
| `win-edulab-mcp` | Operating the MCP servers, long runs in the background |
| `win-edulab-inventory` | Multi-lab inventory layout and conventions |
| `win-edulab-playbook` | Writing playbooks; `playbooks/` vs `tests/` vs `local/` |
| `win-edulab-vault` | Vault secrets: location, naming, encrypt/decrypt |
| `win-workman-task-syntax` | Task strings and the dispatcher |
| `win-workman-schema` | Package schema variables |
| `win-workman-new-role` | Adding a software role to win_workman |
| `win-workman-pkg-utils` | `pkg_utils` task includes |
| `win-workman-pkg-update` | Bumping a package role to a newer upstream version |
| `win-workman-pkg-test` | Testing package roles on lab VMs |
| `win-workman-seb-config` | Safe Exam Browser client settings |
| `veyon-deploy`, `veyon-reference` | Veyon deployment, access control and LDAP |
| `ansible-jinja2` | Jinja2 expressions and type safety in ansible-core 2.20 |

## Project Structure

```
.
├── ansible.cfg                         # Ansible configuration (default inventory: school)
├── requirements.yaml                   # Collection dependencies (git source)
├── .ansible-lint                       # Linting configuration
├── .mcp.json.example                   # MCP server config template (copy to .mcp.json)
├── CLAUDE.md                           # Directives for the Claude Code agent
├── .claude/
│   ├── settings.json
│   └── skills/                         # Claude Code skills
├── inventories/
│   └── school/                         # Reference inventory (other inventories are gitignored)
│       ├── hosts.yaml                  # Lab host inventory
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── vars.yaml           # Global variables and DC parameters
│       │   │   ├── vault.yaml          # Encrypted secrets (gitignored)
│       │   │   └── vault.yaml.example  # Template for vault.yaml
│       │   ├── servers/vars.yaml       # Subnet and broadcast address
│       │   ├── teachers/vars.yaml      # Veyon master flag and lab groups
│       │   ├── students/vars.yaml      # Veyon client flag
│       │   └── windows11/vars.yaml     # SSH/PowerShell connection settings
│       └── host_vars/
├── playbooks/                          # Shared, reusable playbooks (see above)
├── local/                              # Site-specific and one-off playbooks (gitignored)
├── mcp/
│   ├── server.py                       # MCP server entry point
│   ├── ansible_runner.py               # ansible-playbook subprocess wrapper
│   ├── adhoc.py                        # One-off PowerShell runs
│   ├── runlog.py                       # Run logs and background waiting
│   ├── preflight.py                    # Configuration checks before a run
│   ├── inventory.py                    # hosts.yaml parser
│   ├── pyproject.toml                  # Python dependencies
│   └── requirements.txt
├── bin/
│   └── wmlog                           # Follow a background MCP run
├── logs/                               # MCP run logs (gitignored)
├── tests/                              # Test playbooks and VM lifecycle utilities (see tests/README.md)
├── docs/
│   └── mcp.md                          # MCP server full documentation
└── ansible_collections/                # Populated by ansible-galaxy (gitignored)
```

## Updating Collections

`ansible-galaxy` does not reinstall a collection that is already present, so
updating from the Git sources requires `--force`:

```bash
ansible-galaxy collection install -r requirements.yaml -p . --force
```

## Author

Alessandro Gagliano — [lineadicomando.it](https://lineadicomando.it)

## License

GNU General Public License v3.0 — see [`LICENSE`](LICENSE).

## Disclaimer

This project is provided "as is", without warranty of any kind, express or
implied. The author makes no representations about the suitability of this
software for any purpose and assumes no liability for damages, data loss,
security incidents, or malfunctions arising from its use in any context,
including but not limited to production environments, educational institutions,
or critical infrastructure. Use at your own risk.
