---
name: veyon-deploy
description: Use when installing or configuring Veyon on lab workstations in this project — covers the win_workman veyon role (task strings, master vs agent, keypair lifecycle, lab network objects from inventory) and the troubleshooting that actually applies here. Trigger: veyon, veyon-config, win_workman_veyon_master, win_workman_veyon_labs, authkeys, VeyonService
---

# Veyon deployment — win-edulab project

Veyon is never driven by hand here. Everything goes through
`lineadicomando.win_workman.veyon`, dispatched as a task string. Hand-written
`win_package` / `veyon-cli` tasks duplicate logic the role already implements, and they
skip the idempotency checks it does.

For access-control rules and LDAP/AD wiring — which the role does **not** manage — see
the **veyon-reference** skill.

---

## Task strings

| Task | Effect |
|------|--------|
| `veyon` | Install (or upgrade) Veyon. Adds `/NoMaster` unless the host is a master |
| `veyon-on-master` | Install with the Master GUI, regardless of `win_workman_veyon_master` |
| `veyon-off` | Uninstall (`/S`, via the uninstall helper) |
| `veyon-config` | The whole configuration pass — keypair, auth method, key import, lab objects |
| `veyon-info`, `veyon-download`, `veyon-copy`, `veyon-is_present` | Standard pkg actions |

`veyon-config` accepts a positional arg (`veyon-config-student`), but **`act_config.yaml`
never reads it**. Master vs agent is decided by `win_workman_veyon_master` only.

The project playbook is `playbooks/veyon.yaml` — `veyon` + `veyon-config` against
`lab_win`, overridable with `-e target_hosts=<group>`.

```json
{ "playbook": "veyon", "inventory": "ario_info", "e": { "target_hosts": "teacher" } }
```

---

## Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `win_workman_veyon_master` | `false` | Master host: installs the GUI and imports the **private** key |
| `win_workman_veyon_labs` | `[]` | Inventory groups to reconcile as Veyon locations; masters only |
| `win_workman_veyon_keypairs_dir` | `{{ win_workman_storage_path }}/veyon` | Keypair location on the **controller** |
| `win_workman_veyon_remote_key_dir` | `{{ win_workman_remote_tmp }}\veyon\keys` | Staging dir on the Windows target; wiped at the end |
| `win_workman_veyon_cli_path` | *(auto)* | Explicit `veyon-cli.exe` path; otherwise resolved from PATH then Program Files |
| `win_workman_veyon_lab_force_replace` | `false` | Delete the location before importing instead of reconciling in place |
| `win_workman_veyon_no_log` | `true` | Suppresses key material in the log — leave on |

Set per group, not per host:

```yaml
# group_vars/teachers/vars.yaml
win_workman_veyon_master: true
win_workman_veyon_labs:
  - lab_win

# group_vars/students/vars.yaml
win_workman_veyon_master: false
```

---

## What `veyon-config` does, in order

1. **`keypairs_local`** — `run_once`, on the controller. Ensures an RSA-2048 pair exists
   at `<keypairs_dir>/private/key.pem` and `public/key.pem`, generating it with `openssl
   genpkey` if neither is there, then verifies the two halves match by DER fingerprint.
   If **only one** of the two exists the play fails: delete the survivor and re-run.
2. **`stage_remote_keys`** — copies the public key to the target, or the private key on a
   master (slurped and written with `no_log: true`).
3. **`auth_method`** — forces `Authentication/Method` to key-file via `veyon-cli config
   set`, trying `KeyFileAuthentication`, `key-file`, `keyfile`, `1` in turn. Idempotent:
   a value already matching `/key/i` is left alone.
4. **`import_keys`** — exports the currently installed key, fingerprints both sides on
   the controller, and imports only on mismatch (deleting the old key first). This is why
   re-running `veyon-config` reports no change.
5. **`networkobjects_lab`** — only when `win_workman_veyon_master` is true **and**
   `win_workman_veyon_labs` is non-empty.
6. **`cleanup_keys`** — removes the staged key material from the target.

Steps 3, 4 and 5 notify the `Restart Veyon Service` handler.

The key reference passed to `veyon-cli authkeys` is `<basename of keypairs_dir>/<private|public>`,
i.e. `veyon/private` with the default directory.

---

## Lab network objects

`networkobjects_lab` builds the desired location membership **from the inventory** and
reconciles it against what `veyon-cli networkobjects export` reports. One CSV row per
host, `name;host;mac`, hosts compared case-insensitively and MACs stripped to hex digits,
so cosmetic differences do not count as drift.

Preconditions it asserts, and that are the usual cause of a failure here:

- every group in `win_workman_veyon_labs` exists in the inventory and has hosts
- each lab has at least one host once masters are excluded
- every remaining host defines both `ansible_host` and `ansible_mac`, non-empty

A missing `ansible_mac` on one student PC fails the whole play — that field is not
optional for Veyon (nor for `wol`).

---

## Network ports

| Port | Use |
|------|-----|
| 11100/tcp | Veyon Service — Master → client |
| 11400/tcp | Demo server — teacher screen streaming |

Open on the clients; 11400 matters on the teacher PC for demo mode.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Invalid state: only one of private/public key exists` | A half-deleted keypair under `win_workman_veyon_keypairs_dir` | Delete the remaining `key.pem` and re-run `veyon-config` to regenerate the pair |
| `veyon-cli not found. Set win_workman_veyon_cli_path.` | Non-standard install dir | Set `win_workman_veyon_cli_path` for that host |
| `Missing ansible_host or ansible_mac for host '<h>'` | Inventory gap | Add `ansible_mac` in `hosts.yaml` — see **win-edulab-inventory** |
| `Lab '<g>' has no agent hosts after excluding masters` | The group only contains masters | Point `win_workman_veyon_labs` at the group holding the student PCs |
| Clients invisible in Master | Key never imported, or the two sides disagree on auth method | Re-run `veyon-config` on **both** master and agents; it converges them |
| Location full of stale entries | Drift `networkobjects import` cannot resolve | Re-run with `win_workman_veyon_lab_force_replace: true` |
| Config change not taking effect | Service not restarted | The handler fires on change; check `VeyonService` state with `run_powershell` |

Reading state on a host — through the MCP server, never `ansible -m win_shell`:

```json
{ "script": "Get-Service -Name Veyon* | Select-Object Name, Status, StartType", "l": "teacher" }
```
