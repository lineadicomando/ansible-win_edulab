# Tests

This directory contains playbooks for testing roles and configurations.
Site-specific playbooks (AD users, lab-specific configurations) do not belong
here — they go in `local/` (gitignored).

## Structure

```
tests/
  virsh.yaml           # Utility: VM management via virsh (revert, start, shutdown, ...)
  revert_baseline.yaml # Utility: revert to baseline + wake for arbitrary target (var t)
  lab_cad.yaml         # CAD lab deployment test
  lab_coding.yaml      # Coding lab deployment test
  seb_classroom.yaml   # SEB classroom deployment test
  veyon.yaml           # Veyon deployment test
```

## Test environment

Test VMs are managed on QEMU/KVM from the local host.

`virsh.yaml` resolves inventory targets to KVM VM names via its internal `vm_map`.

| Inventory host | KVM VM name            | OS          | Required snapshot |
|----------------|------------------------|-------------|-------------------|
| `teacher`      | `win11-pc00`           | Windows 11  | `baseline`        |
| `student01`    | `win11-pc01`           | Windows 11  | `baseline`        |
| `student02`    | `win11-pc02`           | Windows 11  | `baseline`        |
| `samba_ad_dc`  | `deb13-samba-dc`       | Debian 13   | `baseline`        |

The inventory groups `lab_win`, `lab_cad`, and `lab_coding` all expand to the three
Windows hosts (`teacher`, `student01`, `student02`).

The `baseline` snapshot is a clean Windows 11 installation with WinRM/SSH configured
and no additional software installed.

> **Note:** `virsh.yaml` uses `become: true` — the user running the playbook must have
> sudo privileges on the local host.

## How tests work

Every test playbook follows the same pattern:

1. Revert the VM to the `baseline` snapshot via `virsh.yaml`
2. Wake the VM via `playbooks/wol.yaml`
3. Run the role or task sequence under test

Steps 1 and 2 are embedded in every test playbook, so running a test directly is
sufficient — no manual preparation needed.

## Running tests

```bash
# From the project root (default inventory is inventories/school/hosts.yaml)
ansible-playbook tests/<test-playbook>.yaml
```

### Manual revert

`revert_baseline.yaml` can be used to prepare a VM without running a test:

```bash
# default target: lab_win
ansible-playbook tests/revert_baseline.yaml

# specific target via variable t
ansible-playbook tests/revert_baseline.yaml -e t=teacher
```

## Test playbooks

### `lab_cad.yaml` — CAD lab

**Target:** `teacher` | **Snapshot:** `baseline`

Runs the structural playbook `playbooks/lab_cad.yaml` against the test VM.

### `lab_coding.yaml` — Coding lab

**Target:** `lab_coding` | **Snapshot:** `baseline`

Runs the structural playbook `playbooks/lab_coding.yaml` against the test VM.

### `seb_classroom.yaml` — SEB Classroom

**Target:** `lab_win` | **Snapshot:** `baseline`

Runs the structural playbook `playbooks/seb_classroom.yaml` against the test VM.

### `veyon.yaml` — Veyon

**Target:** `lab_win` | **Snapshot:** `baseline`

Runs the structural playbook `playbooks/veyon.yaml` against the test VM.
