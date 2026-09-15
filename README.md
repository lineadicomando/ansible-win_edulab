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

---

## Documentation

The complete documentation for the project is divided into thematic sections in the `docs/` folder:

- **[Installation and Initial Setup](docs/installation.md)**
  Requirements, Windows 11 Pro preparation, and Getting Started instructions for the lab setup.
- **[Available Playbooks](docs/playbooks.md)**
  Details, default targets, and usage examples for all available playbooks.
- **[Architecture and Project Structure](docs/architecture.md)**
  Architecture diagram and full directory tree layout.
- **[MCP and Claude Code Integration](docs/claude_code.md)**
  List of Claude Code skills and an overview of the three integrated MCP servers.
- **[MCP Server Documentation](docs/mcp.md)**
  Comprehensive technical manual for installing, configuring, and using the tools provided by the MCP servers.

---

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
