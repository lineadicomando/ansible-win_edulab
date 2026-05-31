# EduLab Management

Ansible project for managing a didactic computer lab: a Samba 4 Active
Directory Domain Controller on Debian and Windows 11 workstations.

An **MCP server** (Model Context Protocol) exposes lab operations to Claude Code,
enabling natural-language management of workstations directly from the AI
assistant. A set of **Claude Code skills** embedded in the project assists in
writing playbooks, roles, and configurations following project conventions —
both are first-class features of the project alongside the Ansible automation.

> **Status:** This project is in early development and currently has a
> demonstrative scope. Production use requires substantial adaptation and
> customization to match the specific infrastructure, security policies, and
> operational requirements of each environment.

## Architecture

```
ansible-win_edulab                       ← this project (inventory + playbooks)
    requires ↓
    lineadicomando.win_workman           ← Windows software & system management
    lineadicomando.samba_ad_dc           ← Samba 4 AD DC provisioning on Debian
```

## Requirements

- Ansible >= 2.16
- Git
- An SSH key for the managed hosts (see `inventories/school/group_vars/all/vars.yaml`)

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url> ansible-win_edulab
cd ansible-win_edulab
```

### 2. Create the vault password file

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

### 4. Install Ansible collections

```bash
ansible-galaxy collection install -r requirements.yaml -p .
```

Collections are installed into `./ansible_collections/` (gitignored).
Re-run this command to update to the latest version of each collection.

### 5. Customize the inventory

Edit `inventories/school/hosts.yaml` with the actual IP addresses of your lab hosts:

```yaml
servers:
  hosts:
    samba_ad_dc:
      ansible_host: <DC-IP>

teachers:
  hosts:
    teacher:
      ansible_host: <teacher-IP>

students:
  hosts:
    student01:
      ansible_host: <student1-IP>
    student02:
      ansible_host: <student2-IP>
```

Edit `inventories/school/group_vars/all/vars.yaml` to set the SSH key path and
any collection-level defaults.

### 6. Configure the Samba DC parameters

Edit the `samba_dc_build_*` variables in `inventories/school/group_vars/all/vars.yaml`:

```yaml
samba_dc_build_realm: CMDLN.INTERNAL         # Kerberos realm (uppercase)
samba_dc_build_domain: CMDLN                 # NetBIOS domain name
samba_dc_build_fqdn: dc.cmdln.internal
samba_dc_build_search_domain: cmdln.internal
samba_dc_build_address: 172.16.0.3           # static IP of the DC
samba_dc_build_netmask: 255.255.255.0
samba_dc_build_gateway: 172.16.0.1
samba_dc_build_ifname: enp1s0               # network interface name
samba_dc_build_nameserver: 127.0.0.1        # DC is its own DNS server
samba_dc_build_ntp_server: 172.16.0.1       # upstream NTP server
samba_dc_build_ntp_allow_network: 172.16.0.0/16
```

## Available Playbooks

All playbooks accept `-e target_hosts=<group|host>` to override the default target.

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

```bash
# Install Chrome and Python 3.14
ansible-playbook playbooks/win_wm.yaml -e "t=chrome,python314"

# Uninstall Firefox
ansible-playbook playbooks/win_wm.yaml -e "t=firefox-off"

# Windows Update, then restart
ansible-playbook playbooks/win_wm.yaml -e "t=wu-run,restart"

# Target a specific group
ansible-playbook playbooks/win_wm.yaml -e "t=chrome" -l teachers
```

Task format: `<software>[-<action>]` — default action is `on` (install).
Common actions: `on`, `off`, `download`, `info`.

Available tasks include: `chrome`, `firefox`, `edge`, `brave`, `libreoffice`,
`gimp`, `inkscape`, `vscode`, `python310`–`python314`, `zoom`, `veyon`,
`wu-run`, `wu-pause`, `restart`, `shutdown`, `lock-on/off`, `wallpaper`, …

### `lab_cad.yaml` — CAD lab packages

Installs the CAD lab software set: LibreOffice, Chrome, SketchUp 2026,
AutoCAD LT 2026, TinyCAD.

```bash
ansible-playbook playbooks/lab_cad.yaml
```

### `lab_coding.yaml` — Coding lab packages

Installs the coding lab software set: LibreOffice, Chrome, Edge, Firefox,
Brave, GIMP, Inkscape, ntop, p7zip, PureData, Postman, VS Code, Python 3.14,
Embarcadero Dev-C++.

```bash
ansible-playbook playbooks/lab_coding.yaml
```

### `veyon.yaml` — Veyon classroom management

Installs and configures Veyon on all lab workstations. Teachers are
configured as Veyon masters; students as clients.

```bash
ansible-playbook playbooks/veyon.yaml
```

### `maintenance.yaml` — Routine maintenance

Locks workstations, runs Windows Update, SFC and WIM integrity checks,
updates Chrome and Edge, resets wallpaper, pauses future Windows Update,
disables Microsoft account prompts, then restarts and unlocks.

```bash
ansible-playbook playbooks/maintenance.yaml
```

### `autologon.yaml` — Windows autologon

Configures (or removes) Windows autologon on lab workstations.

```bash
ansible-playbook playbooks/autologon.yaml
```

### `wol.yaml` — Wake on LAN

Sends a Wake-on-LAN magic packet to the target hosts.

```bash
ansible-playbook playbooks/wol.yaml
```

### `seb_classroom.yaml` — Safe Exam Browser for Google Classroom

Installs and deploys Safe Exam Browser pre-configured for Google Classroom,
with URL filtering that allows Google domains and blocks Gemini and NotebookLM.

```bash
ansible-playbook playbooks/seb_classroom.yaml
# Override the Google Workspace domain for the account chooser
ansible-playbook playbooks/seb_classroom.yaml -e win_workman_seb_account_chooser=school.edu
```

## MCP Server (Claude Code integration)

The `mcp/` directory contains an MCP server that exposes the project to Claude Code,
enabling natural-language management of lab workstations.

For full documentation see [`docs/mcp.md`](docs/mcp.md).

### 1. Install Python dependencies

```bash
pip install --user mcp pyyaml
```

Or use a virtual environment to keep the dependencies isolated:

```bash
python3 -m venv mcp/.venv
mcp/.venv/bin/pip install -e mcp/
# Then update the "command" in .mcp.json to point at mcp/.venv/bin/python3
```

### 2. Configure `.mcp.json`

`.mcp.json` is gitignored because it contains machine-specific absolute paths.
Copy the provided template and update the paths for your environment:

```bash
cp .mcp.json.example .mcp.json
# Edit .mcp.json with the actual paths on your machine
```

Restart Claude Code after editing `.mcp.json` or installing dependencies.

### Available tools

**win-edulab** (this project's MCP server):

| Tool | Description |
|------|-------------|
| `get_inventory` | Returns hosts and groups with IPs for a given inventory |
| `run_playbook` | Runs a playbook from the `playbooks/` directory |

**win-workman** (from the `lineadicomando.win_workman` collection):

| Tool | Description |
|------|-------------|
| `get_role_info` | Returns display name, available tasks, and defaults for a win_workman role |
| `run_tasks` | Runs one or more win_workman tasks on lab hosts |

### Example interaction

```
User:    install VLC on teacher
Agent:   Command to run:
           ansible-playbook -i inventories/school/hosts.yaml \
             -l teacher playbooks/win_wm.yaml -e '{"t":"vlc"}'
         Proceed?
User:    yes
Agent:   [runs — PLAY RECAP: teacher ok=31 changed=1]
```

## Project Structure

```
.
├── ansible.cfg                         # Ansible configuration
├── requirements.yaml                   # Collection dependencies (git source)
├── .ansible-lint                       # Linting configuration
├── .mcp.json.example                   # MCP server config template (copy to .mcp.json)
├── inventories/
│   └── school/
│       ├── hosts.yaml                  # Lab host inventory
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── vars.yaml           # Global variables and DC parameters
│       │   │   ├── vault.yaml          # Encrypted secrets (gitignored)
│       │   │   └── vault.yaml.example  # Template for vault.yaml
│       │   ├── teachers/vars.yaml      # Veyon master flag and lab groups
│       │   ├── students/vars.yaml      # Veyon client flag
│       │   └── windows11/vars.yaml     # SSH/PowerShell connection settings
│       └── host_vars/
│           └── samba-ad-dc.yaml
├── playbooks/
│   ├── samba_dc_build.yaml
│   ├── samba_dc_join.yaml
│   ├── win_wm.yaml
│   ├── lab_cad.yaml
│   ├── lab_coding.yaml
│   ├── veyon.yaml
│   ├── maintenance.yaml
│   ├── autologon.yaml
│   ├── wol.yaml
│   └── seb_classroom.yaml
├── mcp/
│   ├── server.py                       # MCP server entry point
│   ├── ansible_runner.py               # ansible-playbook subprocess wrapper
│   ├── inventory.py                    # hosts.yaml parser
│   └── pyproject.toml                  # Python dependencies
├── tests/                              # Test playbooks and VM lifecycle utilities
├── docs/
│   └── mcp.md                          # MCP server full documentation
└── ansible_collections/                # Populated by ansible-galaxy (gitignored)
```

## Updating Collections

```bash
ansible-galaxy collection install -r requirements.yaml -p . --force
```

## Author

Alessandro Gagliano — [lineadicomando.it](https://lineadicomando.it)

## Disclaimer

This project is provided "as is", without warranty of any kind, express or
implied. The author makes no representations about the suitability of this
software for any purpose and assumes no liability for damages, data loss,
security incidents, or malfunctions arising from its use in any context,
including but not limited to production environments, educational institutions,
or critical infrastructure. Use at your own risk.
