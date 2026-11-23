# Tests

This directory contains playbooks for testing roles and configurations.
Site-specific playbooks (real AD users, lab-specific configurations) do not
belong here — they go in `local/` (gitignored). The fictitious test accounts
created by `samba_dc_users.yaml` are part of the test environment and stay here.

## Structure

Three kinds of files live here. A test reverts its VMs to `baseline`, wakes them,
runs, and asserts every step: a green run is a passing test.

**Tools** — drive and build the VMs, assert nothing:

| File | What it does |
|---|---|
| `virsh.yaml` | VM management via virsh: `snapshot-revert`, `start`, `shutdown`, `reboot`, `reset` |
| `vm_build_windows.yaml` | Builds a Windows test VM from scratch, unattended, up to its `baseline` |
| `vm_build_dc.yaml` | Builds the Debian VM of the DC from scratch, preseeded, up to its `baseline` |
| `vm_build/` | Answer file, first-logon script and preseed templates of the two above |

**Fixtures** — the test domain, built on the VMs for the tests that need one:

| File | What it does |
|---|---|
| `requirements.yaml` | Collections needed by the domain tests only (`lineadicomando.samba_dc`) |
| `samba_dc.yaml` | The whole environment: baseline revert, Samba AD DC, test users, domain join of the Windows hosts (`-e domain_hosts=teacher` for one) |
| `samba_dc_build.yaml` | The Samba AD DC alone, from its baseline |
| `samba_dc_provision.yaml` | The `samba_dc_build` role on the DC (imported by the two above) |
| `samba_dc_users.yaml` | Domain test users and groups (imported by `samba_dc.yaml` and `samba_share.yaml`) |

**Tests**:

| File | What it tests | VMs |
|---|---|---|
| `wf_step.yaml` | The shared body of the playbooks as workflow steps: hosts that do not answer, hosts that fail, `wf_tolerant`, what is passed on; `maint_lock`, `maint_unlock` and `wf_report` on top of it | one Windows |
| `deploy.yaml` | A deployment playbook (`-e pb=veyon`, `seb_classroom`, `lab_coding`, `lab_cad`) installs what it lists | `win_managed`, or `-e test_hosts=` |
| `lock.yaml` | `lock`: on/off give back notice, last username setting and logon right; repeated calls, fallback users, reset | one Windows |
| `autoshutdown.yaml` | `autoshutdown`: schedule forms, validation, off; the task fires daily and weekly, and not on other days | one to three Windows |
| `shutdown_wait.yaml` | `shutdown` waits for the host to go offline, fails on a cancelled shutdown, returns at once with `win_workman_shutdown_wait=false` or `shutdown-no_wait`; no revert | one Windows |
| `shutdown_if_nouser.yaml` | `shutdown-if-nouser`: stays on with an Active or Disconnected session, shuts down without | one Windows |
| `usr_zed.yaml` | Per-user deferred install (`usr` action) with domain users, on `zed`; builds the domain first | DC, one Windows |
| `samba_share.yaml` | Shared folders: SMB access per user, drive mapping at logon, revoke, delete; on a domain that is already up | DC, one Windows |

The roles under test belong to the `lineadicomando.win_workman` collection, which
has no VMs of its own: its tests that need a real Windows are here. The lifecycle
of a single package (`info`, `download`, `copy`, `on`, `is_present`, `off`) is not a
playbook of this directory: it is run task by task when the package is added or
updated.

`tests/wf_step.yaml` reads the outcome of each step from the `ansible.posix.json`
callback: the `ansible.posix` collection ships with the `ansible` package, and is
otherwise installed with `ansible-galaxy collection install ansible.posix`.

## Test environment

Test VMs are managed on QEMU/KVM from the local host, i.e. from the Linux
control node itself: this is the reference setup of the project, and the test
playbooks cannot be used from a Windows control node under WSL2. The libvirt
packages required are listed in
[`docs/installation.md`](../docs/installation.md#preparing-the-control-node), and
[`docs/test-vms.md`](../docs/test-vms.md) covers building the VMs themselves:
ISO download links, `virt-install` options, the `baseline` snapshot, and the
evaluation licence the Windows images are used under.

Each test VM is a host of `inventories/school` that names its libvirt domain in
`libvirt_domain`; `virsh.yaml` and the build playbooks read it from there.

| Inventory host | libvirt domain           | OS          | Built by               | Required snapshot |
|----------------|--------------------------|-------------|------------------------|-------------------|
| `teacher`      | `win_edulab-teacher`     | Windows 11  | `vm_build_windows.yaml` | `baseline`       |
| `student01`    | `win_edulab-student01`   | Windows 11  | `vm_build_windows.yaml` | `baseline`       |
| `dc01`         | `win_edulab-samba-dc`    | Debian 13   | `vm_build_dc.yaml`      | `baseline`       |

The inventory groups `win_managed`, `lab_cad`, and `lab_coding` all expand to the two
Windows hosts (`teacher`, `student01`).

The Windows `baseline` is a clean Windows 11 installation with the inventory account,
OpenSSH Server and no additional software; the DC `baseline` is a plain Debian with SSH
and sudo, before `samba_dc_build` runs.

> **Note:** the user running `virsh.yaml` needs access to `qemu:///system` (the
> `libvirt` group), not sudo.

## The test domain controller

win_edulab works with any AD domain and does not build one. The domain of the test
VMs is a Samba AD DC built by the `lineadicomando.samba_dc` collection of
cockpit-samba-dc, which the project's `requirements.yaml` does not install. The
domain tests (`samba_dc*.yaml`, `samba_share.yaml`, `usr_zed.yaml`) need it:

```bash
ansible-galaxy collection install -r tests/requirements.yaml -p .
```

Without it they stop before running anything, with
`the role 'lineadicomando.samba_dc.samba_dc_build' was not found`.

The domain is described by `win_workman_domain_*` in `group_vars/all`, as on a real
site; the DC's own `samba_dc_build_*` variables are in `group_vars/samba_dc` and
follow from them. `test_domain_netbios` (`group_vars/all/test_vms.yaml`) is the
NetBIOS name, used by the tests on the PCs as the `DOMAIN\user` prefix.

## Domain test users

`samba_dc_users.yaml` creates these accounts on the DC, with the lab password
from the vault (`ansible_vault_password`). `samba_dc.yaml` imports it right
after building the DC, and `samba_share.yaml` before using them; it also runs on
its own against a DC that is already up, without reverting anything:

```bash
ansible-playbook tests/samba_dc_users.yaml
```

| Account | Group |
|---|---|
| `student-alice`, `student-bob` | `Students` |
| `teacher-carol` | `Teachers` |

User names carry dashes on purpose: win_workman task strings split on `-`, and
the per-user install (`<role>-usr-<verb>-<targets>`) must keep them intact. The
playbook is idempotent; an existing account keeps its password, which is set on
creation only.

## How tests work

Every test starts the same way:

1. Revert the VMs to the `baseline` snapshot via `virsh.yaml`
2. Wake them via `playbooks/wol.yaml` — the magic packet reaches the VM through
   [`virsh_wakeonlan`](https://github.com/lineadicomando/virsh_wakeonlan), the
   systemd listener that starts the matching libvirt domain
3. Run `openssh-harden`, then the steps under test, each followed by its assert

Both steps are embedded, so running a test is sufficient — no manual preparation.
`usr_zed.yaml` gets them from `samba_dc.yaml`, which it imports; `samba_share.yaml`
is the exception: it reverts nothing and runs on a domain that is already up, the
one `samba_dc.yaml` or `usr_zed.yaml` left.

To prepare a VM without running a test:

```bash
ansible-playbook tests/virsh.yaml -e vm=teacher -e cmd=snapshot-revert -e snapshot=baseline
ansible-playbook playbooks/wol.yaml -e target_hosts=teacher
```

## Running tests

```bash
# From the project root (default inventory is inventories/school/hosts.yaml)
ansible-playbook tests/<test-playbook>.yaml
```

A Windows VM takes 4 GiB and the DC 2 GiB: check the free memory of the host first,
and name fewer hosts when they do not all fit.

```bash
ansible-playbook tests/wf_step.yaml                              # teacher
ansible-playbook tests/lock.yaml -e vm_host=student01
ansible-playbook tests/autoshutdown.yaml -e test_hosts=teacher,student01
ansible-playbook tests/deploy.yaml -e pb=veyon                   # teacher and student01
ansible-playbook tests/deploy.yaml -e pb=lab_coding -e test_hosts=teacher
ansible-playbook tests/usr_zed.yaml                              # DC and teacher
ansible-playbook tests/samba_dc.yaml -e domain_hosts=teacher && ansible-playbook tests/samba_share.yaml
```

Without VMs, the playbooks are checked with `ansible-lint` from the project root,
which also runs their syntax check.
