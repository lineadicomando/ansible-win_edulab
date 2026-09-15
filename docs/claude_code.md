# MCP and Claude Code Integration

The project integrates three **MCP** (Model Context Protocol) servers that expose the lab operations to Claude Code, enabling the management of workstations via natural language.

## Claude Code Skills

The skills located in `.claude/skills/` are loaded by Claude Code when a user's task matches them. `CLAUDE.md` contains the project directives that the agent follows.

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

## Available MCP Servers

The three MCP servers that expose the project to Claude Code are:

- **win-edulab** — this project's server, in `mcp/`
- **win-workman** — shipped with the `lineadicomando.win_workman` collection
- **samba-ad-dc** — shipped with the `lineadicomando.samba_ad_dc` collection

For complete documentation on how to install, configure, and extend the MCP servers, refer to the [mcp.md](mcp.md) file.
