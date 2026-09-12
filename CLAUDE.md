# CLAUDE.md

Agent instructions and directives for this project.

## Project Directives

### 1. Use MCP services as the primary interface

**Rule**: Always prefer the configured MCP services (win-workman, samba-ad-dc, win-edulab) over direct Ansible shell command execution.

**Why**: MCP services provide a structured and semantic interface that makes operations more traceable, documented, and easier to debug.

**How to apply**:
- To execute tasks on Ansible hosts: use the `run_tasks` tool from the `win-workman` MCP server
- To run a one-off PowerShell command on a Windows host: use the `run_powershell` tool from the `win-edulab` MCP server, never `ansible -m win_shell` in a terminal. The tool inherits the inventory's credentials, records the run under `logs/`, and keeps secrets passed as `sensitive_parameters` out of that record
- Before executing a task, call `get_role_info` if you're unsure which actions are available
- Execute Ansible commands directly via shell only when the task is not available through the configured MCP services

### 1b. MCP services as continuous control tests

**Rule**: Every use of MCP services in normal work is also a test of service health. Never bypass MCP to avoid testing overhead.

**Why**: Using MCP services during regular work catches configuration issues, API breakage, and regressions early. If you skip the MCP layer to "just read the file", you lose visibility into whether the services actually work when needed.

**How to apply**:
- Always route requests through MCP first, even for simple lookups (inventory queries, role info, configuration reads)
- If an MCP call fails, treat it as a real issue to diagnose—do not fall back to direct file reads as a workaround
- Each successful MCP call verifies that the service, credentials, and configuration are working correctly

### 1c. Run long operations in the background, leave the chat free

**Rule**: Any run longer than a few seconds — a package install, a whole-lab run, a pkg lifecycle test — is started with `background=true` and awaited from *outside* the turn, on the `logs/<run>.log.done` sentinel. Never call `wait_run` straight after starting the run.

**Why**: `wait_run` blocks the turn, so a background run followed immediately by `wait_run` behaves exactly like a synchronous one and the chat stays busy for the whole install. Waiting on the sentinel from a backgrounded Bash command lets the harness re-invoke when the run ends, so the user keeps the chat meanwhile.

**How to apply**:
- Start with `run_tasks(..., background=true)`, note the returned log name
- Then, Bash with `run_in_background`: `until [ -f logs/<run>.log.done ]; do sleep 10; done`
- Report the outcome when re-invoked; never watch with `pgrep -f`, which matches the watcher's own command line and never exits
- `wait_run` inline only when the very next step depends on the result; `run_status` reads a run without waiting
- Details and examples: skill `win-edulab-mcp`, section **Long runs**

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


### 4. Write commit messages in English

**Rule**: Git commit messages are always written in English, regardless of the language used in conversation.

**Why**: The conversation language is Italian, but the repository history is a technical artifact meant to stay readable to any contributor and consistent with the code, which is written in English. Mixed-language history is hard to search and to skim.

**How to apply**:
- Subject line in the imperative mood, English: `Add the display_scale role for display scaling`
- Body in English too, including the explanation of trade-offs and the reasoning behind the change
- This applies to commit messages only — conversation, explanations, and answers to the user stay in Italian

### 5. Keep one-off and site-specific playbooks in local/

**Rule**: Playbooks written for a specific task, a single lab, or a local diagnosis go in `local/`, not in `playbooks/`. Only playbooks meant to be shared belong in `playbooks/`, which is tracked by git and published to GitHub.

**Why**: `local/` is listed in `.gitignore`, so it is the place for anything site-specific: host names, lab-specific fixes, throwaway diagnostics. `playbooks/` is the public surface of the repo and should stay readable as a catalogue of reusable operations. Mixing the two pollutes the repository history with content that means nothing outside this installation.

**How to apply**:
- Before creating a playbook, ask whether it would make sense to someone with a different set of labs. If not, write it to `local/`
- A diagnostic written to answer one question is a `local/` playbook, even when it is well written
- Promote a playbook from `local/` to `playbooks/` only when it has been generalised: no hardcoded hosts, no site-specific paths, parameters exposed as variables
- **Caveat**: the `run_playbook` MCP tool resolves names against `playbooks/` only (see `mcp/ansible_runner.py`). Playbooks in `local/` must be run with `ansible-playbook local/<name>.yaml` directly
