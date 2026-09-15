# Architecture and Project Structure

The **ansible-win_edulab** project manages a didactic computer lab consisting of a Domain Controller on Debian and Windows 11 workstations.

## Architecture

The automation is based on Ansible and two dedicated collections:

```
ansible-win_edulab                       ← this project (inventory + playbooks + MCP server)
    requires ↓
    lineadicomando.win_workman           ← Windows software & system management (+ MCP server)
    lineadicomando.samba_ad_dc           ← Samba 4 AD DC provisioning on Debian (+ MCP server)
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
├── docs/                               # Project documentation
│   ├── mcp.md                          # MCP server full documentation
│   ├── installation.md                 # Setup and requirements
│   ├── playbooks.md                    # Available playbooks
│   ├── architecture.md                 # Project structure and layout
│   └── claude_code.md                  # Claude Code integration details
└── ansible_collections/                # Populated by ansible-galaxy (gitignored)
```
