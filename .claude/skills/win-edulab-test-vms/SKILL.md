---
name: win-edulab-test-vms
description: Use when building, starting, reverting or snapshotting the test VMs of this project (QEMU/KVM, libvirt) — covers the inventory fields that describe a VM, the unattended Windows build with tests/vm_build_windows.yaml and the preseeded DC build with tests/vm_build_dc.yaml, the resource check before starting VMs, tests/virsh.yaml, the baseline snapshot, the evaluation expiry, and the manual fallback when an unattended install stalls
---

# Test VMs — build and lifecycle

The test VMs are the hosts of `inventories/school` that carry `libvirt_domain`. This
skill covers the parts that hold on any workstation; the machines of *this* workstation
(memory, ISO paths, the VMs of other projects, standing permissions) are in
`CLAUDE.local.md`. Read it first.

## Where a VM is described

Everything comes from the inventory, never from a playbook:

| Field | Where | Used by |
|---|---|---|
| `libvirt_domain` | `hosts.yaml`, per host | `tests/virsh.yaml`, build playbooks, `tools/vm/vmgui.py` |
| `ansible_host`, `ansible_mac` | `hosts.yaml`, per host | static IP set in the guest, NIC MAC, `wol` |
| `test_vm_*` (network, pool, size, locale) | `group_vars/all/test_vms.yaml` | build playbooks, `virsh.yaml` |
| `test_vm_win11_iso`, `test_vm_debian_iso` | `local/test_vms.yaml` (untracked) | build playbooks |
| `ansible_user`, `ansible_password` | `group_vars/all` + vault | account created by the build |

When a VM disagrees with the inventory, fix the VM (or rebuild it), not the inventory.

## Before starting any VM: resources

Measure every time; the host may have changed since the last session.

```bash
free -m; nproc; virsh -c qemu:///system list
virsh -c qemu:///system dominfo <domain> | grep -Ei 'memor|cpu'
```

Sum the memory of the running VMs and of the ones to start, compare with the `available`
column. If it does not fit, start fewer VMs and say so. Shut down what you started when
the test is over. `tests/vm_build_windows.yaml` refuses to build VMs that do not fit.

## Building a Windows VM from scratch

```bash
ansible-playbook tests/vm_build_windows.yaml -e vm=teacher \
  > logs/vm_build_teacher.log 2>&1        # Bash run_in_background: 20-40 minutes
```

- Stops if the domain exists; `-e rebuild=true` destroys it first, with disk, NVRAM, TPM
  and snapshots. **Ask the user before passing `rebuild=true`.**
- Steps: answer ISO (`tests/vm_build/autounattend.xml.j2` + `setup.ps1.j2`) built under
  `/tmp` and uploaded to the libvirt pool → `virt-install` (UEFI Secure Boot, TPM 2.0,
  SATA, e1000e, the inventory MAC) → Enter pressed at the "boot from CD" prompt → Setup
  and OOBE unattended → first logon of `ansible_user` runs `setup.ps1` (OpenSSH Server,
  PowerShell as DefaultShell, firewall, no sleep/hibernation, static IP) → SSH check →
  evaluation end date reported → shutdown → media ejected → `baseline` snapshot.
- Build one Windows VM at a time unless memory allows more.
- After the build, write the date and the reported evaluation end in `CLAUDE.local.md`.

### When the build stalls

Look before guessing: `tools/vm/vmgui.py <host> shot` and read the PNG (skill
`win-edulab-vm-gui`).

| Screen / symptom | Cause | What to do |
|---|---|---|
| UEFI shell or "No bootable device" | Enter not received in time | `virsh destroy`, rerun with `rebuild=true` |
| Setup asks for language or disk | answer file not found or rejected | check the second CD is attached (`virsh domblklist`); a typo in the XML makes Setup ignore it |
| "This PC can't run Windows 11" | TPM or Secure Boot missing | check `<tpm>` and the firmware features in `virsh dumpxml` |
| OOBE screen waiting for input | a new OOBE page the answer file does not hide | complete it by hand with vmgui, note the page, extend the template |
| Desktop, but port 22 closed | `setup.ps1` failed | read `C:\Windows\Temp\edulab-setup.log` from the guest console (vmgui: Win+R, `notepad C:\Windows\Temp\edulab-setup.log`) |
| Port 22 on the DHCP address only | static IP step failed | same log; `Get-NetIPAddress` in the guest |

If automation keeps failing, the manual procedure in `docs/test-vms.md` (Windows setup
inside the VM) still applies: guide the user step by step, then take the `baseline`
snapshot shut off.

### For another project

Another project builds its own VM with these playbooks and its own inventory
(`ansible-playbook -i <its inventory> tests/vm_build_windows.yaml -e vm=<host>`).
Requirements and the `.env` pattern: `docs/test-vms.md`, "From another project".
Connection variables go under `win_managed`, never `all` (plays on localhost break).

## Building the DC VM from scratch

```bash
ansible-playbook tests/vm_build_dc.yaml > logs/vm_build_dc01.log 2>&1   # ~10 minutes
```

- Targets the `samba_dc` group; same `rebuild=true` guard and memory check (2 GiB).
- Debian netinst with `tests/vm_build/preseed.cfg.j2` injected in the initrd: static
  address, `ansible_user` with sudo (password hashed with `openssl passwd -6`), SSH,
  python3, qemu-guest-agent. Virtio NIC → `enp1s0`, checked against
  `samba_dc_build_ifname`.
- Then moves the static stanza to `/etc/network/interfaces.d/<iface>` (the file
  `samba_dc_build` writes) and sets `/etc/resolv.conf`, reboots once to prove the
  address survives, shuts down and takes `baseline`. The domain is *not* provisioned:
  `tests/samba_dc_build.yaml` / `tests/samba_dc.yaml` do that from this baseline.
- If the installer stops on a question, take a screenshot: the preseed lacks an
  answer for it. The Debian console is text; `vmgui.py dc01 shot` reads it.
- The guest agent is on: `virsh qemu-agent-command <domain> '{"execute":"guest-exec",...}'`
  runs commands as root when the network is broken.

## Lifecycle with tests/virsh.yaml

```bash
ansible-playbook tests/virsh.yaml -e '{"vm":["teacher"],"cmd":"snapshot-revert","snapshot":"baseline"}'
ansible-playbook tests/virsh.yaml -e '{"vm":["win_managed"],"cmd":"start"}'
```

- `vm` takes inventory hosts or groups; each host must have `libvirt_domain`.
- `cmd`: `snapshot-revert`, `start`, `shutdown`, `reboot`, `reset`. No sudo needed.
- `snapshot-revert` destroys the current state: ask first unless the user asked for a test
  that starts from `baseline`.
- A shut-off `baseline` leaves the VM off after the revert; tests then wake it with
  `playbooks/wol.yaml` (needs the `virsh_wakeonlan` listener, see `docs/test-vms.md`).
- After a revert `secure_ssh` must run again before key-based SSH works.

## Snapshots

- `baseline`: clean OS, the inventory account, SSH; shut off. Taken by the build playbook.
- Before an experiment that dirties a VM outside a test playbook, create a named snapshot
  of the current state and revert to it at the end.
- Layered snapshots across VMs (DC provisioned + Windows joined) must be reverted
  together: Windows rotates its machine account password, and a DC reverted alone no
  longer trusts it.

## Evaluation licence

Windows 11 Enterprise Evaluation runs 90 days from installation (licence terms in
`docs/test-vms.md`). The build playbook reports the end date; when it is near, rebuild
with `rebuild=true` from a freshly downloaded ISO rather than rearming an old image.
