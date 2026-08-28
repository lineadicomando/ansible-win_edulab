# CLAUDE.md

Agent instructions and directives for this project.

## Project Directives

### 1. Use MCP services as the primary interface

**Rule**: Always prefer the configured MCP services (win-workman, samba-ad-dc, win-edulab) over direct Ansible shell command execution.

**Why**: MCP services provide a structured and semantic interface that makes operations more traceable, documented, and easier to debug.

**How to apply**:
- To execute tasks on Ansible hosts: use the `run_tasks` tool from the `win-workman` MCP server
- Before executing a task, call `get_role_info` if you're unsure which actions are available
- Execute Ansible commands directly via shell only when the task is not available through the configured MCP services

### 2. Detect and handle missing essential configuration

**Rule**: Before attempting to execute MCP tasks, proactively detect missing essential configuration (inventories, encrypted vaults, SSH keys) and signal the issue clearly to the user.

**Why**: Missing configuration causes silent failures or cryptic errors. Early detection prevents user frustration and blocks work clearly rather than letting it fail mid-execution.

**How to apply**:
- **Preventive check**: Before calling `run_tasks`, verify that:
  - The requested inventory exists (default is `school`)
  - Ansible vault files are present and accessible (if secrets are needed)
  - SSH keys or connection credentials are configured in the inventory
- **Clear signaling**: When configuration is missing, explicitly list what is missing:
  - Example: "Inventory 'ario_info' not found. Available inventories: school"
  - Example: "Vault for 'ario_info' inventory is not initialized. Encrypted secrets will not be available"
- **Offer guidance (do not impose)**: Suggest next steps:
  - Recommend relevant skills: `ansible-vault-secrets`, `win-edulab-vault`, `win-edulab-inventory`
  - Offer to guide the user through initialization if they want to proceed
  - Provide links to configuration files or documentation
- **Proceed only if user confirms**: If configuration is missing, wait for user approval before attempting workarounds or alternative approaches

### 3. Discover available roles and actions via MCP

**Rule**: When unsure about available roles or their supported actions, use the `get_role_info` tool from the `win-workman` MCP server as the authoritative source.

**Why**: The win-workman collection contains 80+ roles with various actions (install, remove, configure, etc.). Rather than maintaining a static list in code, the MCP server provides real-time, accurate documentation.

**How to apply**:
- To list all available roles: call `list_roles` implicitly by checking the `win-workman` MCP server documentation
- To inspect a specific role: use `get_role_info("role_name")` to get:
  - Display name
  - Available custom actions
  - Configurable defaults
  - Additional notes
- **Common task patterns** (examples):
  - Install/enable: `chrome`, `firefox`, `vscode`, `git`, `python312`
  - System control: `shutdown`, `restart`, `lock`, `logoff`
  - Network/diagnostics: `ping`, `chkdsk`, `sfc`
  - Desktop management: `wallpaper`, `oobe`, `autologon`
- When a user requests a task, check if a corresponding role exists before executing. If unsure, call `get_role_info` to verify the role name and available actions

