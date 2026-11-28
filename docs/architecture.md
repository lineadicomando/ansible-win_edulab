# Architecture and Project Structure

The **ansible-win_edulab** project manages a didactic computer lab consisting of Windows 11 workstations, optionally joined to an Active Directory domain served by a DC this project does not manage.

Everything runs from a **Linux control node** — Ansible, the MCP servers, and the
QEMU/KVM test VMs that the playbooks in `tests/` revert and start through
`virsh`. A Windows control node under WSL2 is supported for compatibility, with
the test environment unavailable; see
[Installation](installation.md#preparing-the-control-node).

## Architecture

The automation is based on Ansible and one dedicated collection:

```
ansible-win_edulab                       ← this project (inventory + playbooks + MCP server)
    requires ↓
    lineadicomando.win_workman           ← Windows software & system management (+ MCP server)

tests/ only (tests/requirements.yaml) ↓
    lineadicomando.samba_dc              ← builds the Samba 4 AD DC of the test VMs
                                           (cockpit-samba-dc)
```

## Project Structure

The organization of files and folders within the project is as follows:

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
├── .fleet/skills/                      # Skills for the assistant of cockpit-fleet
├── inventories/
│   └── school/                         # Reference inventory (other inventories are gitignored)
│       ├── hosts.yaml                  # Lab host inventory
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── vars.yaml           # Global variables, lab network and DC parameters
│       │   │   ├── vault.yaml          # Encrypted secrets (gitignored)
│       │   │   └── vault.yaml.example  # Template for vault.yaml
│       │   ├── teachers/vars.yaml      # Veyon master flag and lab groups
│       │   ├── students/vars.yaml      # Veyon client flag
│       │   └── win_managed/vars.yaml       # SSH/PowerShell connection settings
│       └── host_vars/
├── playbooks/                          # Shared, reusable playbooks (see above)
├── local/                              # One-off playbooks and workstation files (gitignored)
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
├── tools/                              # vm/vmgui.py (test VM desktop), win_usb.sh (ISO to UEFI USB stick)
├── tests/                              # Test playbooks and VM lifecycle utilities (see tests/README.md)
├── docs/                               # Project documentation
│   ├── mcp.md                          # MCP server full documentation
│   ├── installation.md                 # Setup and requirements
│   ├── test-vms.md                     # Building the QEMU/KVM test VMs (and their licensing)
│   ├── playbooks.md                    # Available playbooks
│   ├── architecture.md                 # Project structure and layout
│   └── claude_code.md                  # Claude Code integration details
└── ansible_collections/                # Populated by ansible-galaxy (gitignored)
```
