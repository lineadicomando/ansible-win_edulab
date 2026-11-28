# CLAUDE.md

Directives for the agent. Conversation in Italian; code, docs and commits in English.

## 1. Scope: development, not operations

This repository and the collection win_workman (a separate repo, pinned in
`requirements.yaml`) are developed and tested here against the test VMs of the `school`
inventory. Real labs are operated from cockpit-fleet, which runs a clone of what is
pushed: do not run tasks on real lab hosts from here, and keep no site data in this
workspace.

The repos are public. Tracked files and commit messages never name a real site, lab,
host, domain, network or account; examples use `school`, its test VMs or generic names
(`lab_a`, `PC01`, `<inventory>`). Commit messages do not name the test hosts either
("a Windows test VM", not the host name).

## 2. MCP first, also as a health check

- Tasks: `run_tasks` (win-workman). One-off PowerShell: `run_powershell` (win-edulab),
  never `ansible -m win_shell`: it inherits the inventory's credentials, logs under
  `logs/` and keeps `sensitive_parameters` out of the log. Playbooks: `run_playbook`
  (names resolve against `playbooks/` only). Hosts and groups: `get_inventory`.
- Roles and actions: `get_role_info` (the 90+ roles of win_workman); check that a role
  exists before running it.
- Route lookups through MCP too: each call tests the services. If a call fails, diagnose
  it as a real issue instead of reading the files around it. Shell Ansible only for what
  MCP cannot do.
- The Samba DC of the test VMs is a fixture (`tests/requirements.yaml`): prefer the
  `samba-dc`/`addcctl` servers of cockpit-samba-dc for it when configured.

## 3. Long runs in the background

Anything longer than a few seconds starts with `background=true`; then wait from a
backgrounded Bash on the sentinel, `until [ -f logs/<run>.log.done ]; do sleep 10; done`,
and report when re-invoked. Never `wait_run` straight after the start (it blocks the
chat), never `pgrep -f` (it matches the watcher). `wait_run` inline only when the next
step needs the result; `run_status` reads without waiting. Details: skill
`win-edulab-mcp`, **Long runs**.

## 4. Missing configuration: stop and say what is missing

Before `run_tasks`, check that the inventory exists (default `school`), its vault is
readable and the connection credentials are set (`mcp/preflight.py` checks the same).
If something is missing, name it ("Inventory 'lab_a' not found. Available: school"),
point to the skills `win-edulab-inventory` / `win-edulab-vault`, and wait for the user
before any workaround.

## 5. Commits

English, imperative subject (`Add the display_scale role for display scaling`), body
with the reasoning. Grep diff and message for site data (§1) before committing. Push
only to `origin`. A collection release goes through its `tools/release.sh` (atomic push
of branch and tag, then the pin here): skill `win-workman-pkg-update`.

## 6. local/ for one-off files

`local/` is gitignored: one-off diagnostics and workstation files (`local/test_vms.yaml`,
ISO paths for the VM builds). `playbooks/` is the public, reusable catalogue: promote a
playbook only when generalised (no hardcoded hosts or paths, parameters as variables).
`run_playbook` cannot run `local/` playbooks: use `ansible-playbook local/<name>.yaml`.

## 7. Test VMs

How to build, start, revert and drive them: skills `win-edulab-test-vms`,
`win-edulab-vm-gui`. Which machines, ISOs and resources this workstation has, and the
standing permissions: `CLAUDE.local.md` (untracked; if missing, ask). The `school`
inventory is the source of truth for names, addresses and MACs. Check free memory before
every start; build with `tests/vm_build_windows.yaml` / `tests/vm_build_dc.yaml`; ask
before building, rebuilding, deleting or reverting; never touch libvirt domains that the
inventory does not name.

## Where things are

`docs/architecture.md` (layout), `docs/installation.md`, `docs/mcp.md` (servers, tools,
logs), `docs/playbooks.md` (catalogue, cockpit-fleet workflows), `docs/test-vms.md`,
`tests/README.md` (test playbooks), `docs/claude_code.md` (skills). Open work:
`TODO.local.md` here, `TODO.md` in the collection.
