---
name: win-workman-pkg-test
description: Use when testing win_workman package roles against lab VMs — covers VM lifecycle (snapshot revert, wake-on-LAN, SSH setup), the manual test command pattern, and the standard action sequence for pkg role validation
---

# win_workman Package Role Testing

## Overview

Testing a package role means running each standard pkg action against a known-clean VM,
verifying both that changes happen and that the role is idempotent. All commands go
through `playbooks/win_wm.yaml` via the `-l <host>` limit and `-e '{"t":"<task>"}'` extra var.

---

## VM lifecycle

### 1. Revert to baseline snapshot

```bash
ansible-playbook tests/virsh.yaml -e '{"vm":["teacher"],"cmd":"snapshot-revert","snapshot":"baseline"}'
```

`vm` accepts inventory hostnames or group names. The playbook maps them to virsh VM names
via `vm_map`. After revert the VM is powered off.

### 2. Power on (Wake-on-LAN)

```bash
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"wol"}'
```

### 3. Authorize SSH key access

Run once after each snapshot revert to set up key-based SSH so subsequent plays do not
prompt for credentials:

```bash
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"secure_ssh"}'
```

### SSH access for manual verification

| Host | Command |
|------|---------|
| teacher | `ssh maint@172.16.2.10` |
| student01 | `ssh maint@172.16.2.11` |
| student02 | `ssh maint@172.16.2.12` |

---

## Test command pattern

```bash
ansible-playbook -l <host> playbooks/win_wm.yaml -e '{"t":"<schema>[-<action>]"}'
```

- `-l <host>` — limit to a single inventory host (e.g., `teacher`, `student01`)
- `t` — task string forwarded to the dispatcher; omitting the action defaults to `on`

Multiple tasks in one run (comma-separated):

```bash
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-download,chrome-copy,chrome"}'
```

---

## Standard action test sequence for a package role

Run in this order to exercise the full pkg lifecycle. Replace `chrome` with the schema
under test.

| Step | Command | Expected result |
|------|---------|-----------------|
| 1 | `chrome-info` | Reports absent; no changes |
| 2 | `chrome-download` | Downloads installer to controller cache; target unchanged |
| 3 | `chrome-copy` | Copies installer to `C:\Windows\Temp\ansible`; no install |
| 4 | `chrome` (= `chrome-on`) | Installs; `changed=true` |
| 5 | `chrome` again | Idempotent; `changed=false` |
| 6 | `chrome-info` | Reports present + installed version |
| 7 | `chrome-is_present` | Passes (software is installed) |
| 8 | `chrome-off` | Uninstalls; `changed=true` |
| 9 | `chrome-is_present` | **Fails** (expected — software is absent) |
| 10 | `chrome-info` | Reports absent; no changes |

### Example commands (chrome)

```bash
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-info"}'
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-download"}'
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-copy"}'
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome"}'
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-on"}'
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-is_present"}'
ansible-playbook -l teacher playbooks/win_wm.yaml -e '{"t":"chrome-off"}'
```

---

## Writing a test playbook in tests/

For a full lifecycle test that can be re-run cleanly, follow this structure:

```yaml
---
# tests/<role>.yaml
- ansible.builtin.import_playbook: virsh.yaml
  vars:
    vm: ["teacher"]
    cmd: snapshot-revert
    snapshot: baseline

- name: Wake target VM
  ansible.builtin.import_playbook: ../playbooks/win_wm.yaml
  vars:
    hosts: teacher
    t: wol

- name: Authorize SSH
  ansible.builtin.import_playbook: ../playbooks/win_wm.yaml
  vars:
    hosts: teacher
    t: secure_ssh

- name: Lifecycle test — <schema>
  hosts: teacher
  gather_facts: false
  roles:
    - role: lineadicomando.win_workman.dispatcher
      vars:
        win_workman_tasks:
          - <schema>-info
          - <schema>-download
          - <schema>-copy
          - <schema>
          - <schema>-info
          - <schema>-is_present
          - <schema>-off
          - <schema>-info
```

---

## What each action tests

| Action | What to verify |
|--------|---------------|
| `info` | Returns `win_workman_is_present` and `win_workman_installed_version`; `changed=false` always |
| `download` | File appears in `win_workman_storage_path` on controller; target not touched |
| `copy` | File appears in `C:\Windows\Temp\ansible` on target; not installed |
| `on` | Software installed; registry entry present; shortcuts created if defined |
| `on` (repeat) | `changed=false`; version not downgraded |
| `is_present` | Play continues if installed; fails with clear message if absent |
| `off` | Software removed; cleanup_paths removed; shortcuts removed |

---

## Troubleshooting

- **`is_present` fails unexpectedly after `on`** — check `product_id` / `detect_display_name`
  in the schema; the registry detection may not match the installed entry.
- **`off` does not remove the package** — verify `uninstall_product_id` or
  `uninstall_display_name` in the schema matches the actual registry value (use `info` to read it).
- **`download` re-downloads every run** — `checksum` field in the schema is missing or wrong.
- **`copy` fails** — `win_workman_remote_tmp` dir does not exist or WinRM/SSH not accessible;
  run `secure_ssh` task first and confirm connectivity with `ssh maint@<ip>`.
