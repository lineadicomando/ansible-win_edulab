# Test VMs (QEMU/KVM)

The playbooks in [`tests/`](../tests/README.md) run against local virtual
machines: they revert a VM to its `baseline` snapshot, wake it, and then apply
the role under test. This page describes how those VMs are built, and the
licensing terms that apply to the Windows images used for them.

---

## Licensing

This project is open, experimental and demonstrative. It has no commercial use
and none is planned, but that does not remove the need to run the test VMs on
software you are entitled to use.

**This repository never ships Windows images, product keys, or activation
workarounds.** The ISO is downloaded from Microsoft, by you, from the official
Evaluation Center, and used within the terms below.

### Windows 11 Enterprise Evaluation

- Product page — [microsoft.com/evalcenter/evaluate-windows-11-enterprise](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise)
  ([IT](https://www.microsoft.com/it-it/evalcenter/evaluate-windows-11-enterprise))
- Download — [microsoft.com/evalcenter/download-windows-11-enterprise](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise)
  ([IT](https://www.microsoft.com/it-it/evalcenter/download-windows-11-enterprise))

The ISO is the full product, valid for **90 days**, and requires no product key.
Microsoft addresses it to "IT professionals interested in trying Windows 11
Enterprise on behalf of their organization". The governing clause is in the
Windows Operating System license terms, under *Limited rights versions*:

> **Evaluation.** For evaluation (or test or demonstration) use, you may not
> sell the software, use it in a live operating environment, or use it after the
> evaluation period.

What that means for this project:

- **In scope.** The VMs are disposable targets used to validate roles and
  playbooks before they touch real hardware. No user is served by them and no
  service runs on them: this is test and evaluation use.
- **Out of scope.** Promoting one of these VMs to a working machine, a demo box
  left running for an audience, or any kind of server. That is a live operating
  environment and the evaluation license does not cover it.
- **The 90-day clock is part of the licence, not an inconvenience.** When the
  evaluation expires — black wallpaper, "not genuine" notice, hourly shutdown —
  rebuild the VM from a freshly downloaded ISO and take a new `baseline`
  snapshot. Snapshot reverts are there to reset the *test state* within the
  evaluation period; they are not a way to keep an expired image alive.
- Inside the guest, `slmgr /dlv` reports the days left and the remaining rearm
  count; `slmgr /rearm` resets the timer the number of times Microsoft allows
  for the edition. Both are stock Windows mechanisms.

> **Fidelity note:** the evaluation media is Windows 11 **Enterprise**, while
> the managed hosts in a real lab are Windows 11 **Pro**. Package installs,
> Veyon and SEB behave the same, but Enterprise-only policies, AppLocker and
> some Windows Update defaults do not: a green test does not automatically
> transfer to a Pro workstation.

### Debian 13 (Domain Controller)

The DC VM uses the standard Debian netinst image from
[debian.org/distrib](https://www.debian.org/distrib/). Debian is free software:
no evaluation window and no rebuild deadline apply to that VM.

---

## Host prerequisites

The control node runs the VMs locally through libvirt — see
[Installation](installation.md#preparing-the-control-node) for the base
packages. Windows 11 additionally needs UEFI Secure Boot and an emulated TPM
2.0, so the firmware and swtpm packages must be present:

```bash
# Fedora
sudo dnf install -y qemu-kvm libvirt virt-install virt-manager edk2-ovmf swtpm swtpm-tools

# Debian / Ubuntu
sudo apt install -y qemu-system-x86 libvirt-daemon-system libvirt-clients \
                    virtinst virt-manager ovmf swtpm swtpm-tools
```

The VMs live on the system libvirt instance (`qemu:///system`). The user running
the playbooks needs access to it — membership of the `libvirt` group — but no sudo.
The build playbooks also need `xorriso` (to pack the Windows answer file) and
`openssl` (to hash the Debian password).

### Wake-on-LAN for libvirt domains

Every test playbook wakes its target through `playbooks/wol.yaml`, which sends a
magic packet exactly as it would to a physical workstation. A libvirt domain has
no firmware listening for one, so the host needs a translator:
[**virsh_wakeonlan**](https://github.com/lineadicomando/virsh_wakeonlan) is a
small systemd service that receives the packet, matches the MAC against the
defined domains, and starts the right VM with `virsh`. It is what keeps the test
playbooks identical to the ones used against real hardware.

```bash
git clone https://github.com/lineadicomando/virsh_wakeonlan.git
cd virsh_wakeonlan
sudo make install
systemctl status virsh_wakeonlan.service
```

The listener binds UDP ports `7`, `9` and `40000`; with `firewalld` they must be
open in the zone of the libvirt bridge:

```bash
sudo firewall-cmd --get-zone-of-interface=virbr0
sudo firewall-cmd --zone=<zone> --add-port={7,9,40000}/udp --permanent
sudo firewall-cmd --reload
```

Without this service the test playbooks still revert the snapshot, but the wake
step waits 300 seconds on port 22 and fails unless the VM is started by hand.

---

## Network and addressing

The test lab sits on the libvirt `default` NAT network, `192.168.122.0/24`,
whose gateway `192.168.122.1` is also the DNS forwarder and NTP source declared
in `inventories/school/group_vars/all/`.

Everything that describes a VM is in the inventory: address and MAC in
`hosts.yaml`, together with `libvirt_domain`, the name of the VM; sizes, network,
locale and timezone of the guests in `group_vars/all/test_vms.yaml`. The build
playbooks and `tests/virsh.yaml` read them from there, so renaming a VM or moving
it to another address means editing the inventory and rebuilding the VM.

| Inventory host | libvirt domain          | IP               | MAC                 |
|----------------|-------------------------|------------------|---------------------|
| `dc01`         | `win_edulab-samba-dc`   | `192.168.122.20` | `52:54:00:ed:1a:20` |
| `teacher`      | `win_edulab-teacher`    | `192.168.122.21` | `52:54:00:ed:1a:21` |
| `student01`    | `win_edulab-student01`  | `192.168.122.22` | `52:54:00:ed:1a:22` |

Addresses are **static inside each guest**, below the libvirt DHCP range
(`.100`–`.200`), so nothing depends on a lease. The MAC matters as well: the
`wol` role sends its magic packet to `ansible_mac`, and `virsh_wakeonlan` starts
the domain whose NIC carries it. Other projects may keep VMs on the same libvirt
network: give each VM its own address and MAC, or the listener cannot tell them
apart.

---

## Building the VMs

The ISOs are downloaded by you (links above) and their paths given to the
playbooks as `test_vm_win11_iso` and `test_vm_debian_iso`, either with `-e` or in
`local/test_vms.yaml`, an untracked file the playbooks load when present:

```yaml
---
test_vm_win11_iso: /path/to/Win11_Enterprise_Eval.iso
test_vm_debian_iso: /path/to/debian-13-amd64-netinst.iso
```

Each playbook stops if the VM already exists; `-e rebuild=true` destroys it first,
with its disk, NVRAM, TPM and snapshots. Both check that the host has the memory
the VM needs before creating it. They need `virt-install`, `xorriso` and `openssl`
on the control node, and Internet access for the guests.

### Windows: `tests/vm_build_windows.yaml`

```bash
ansible-playbook tests/vm_build_windows.yaml -e vm=teacher      # 20-40 minutes
ansible-playbook tests/vm_build_windows.yaml -e vm=student01
```

One VM at a time is the safe default: each takes 4 GiB of RAM. The playbook:

1. renders an answer file (`tests/vm_build/autounattend.xml.j2`) and a first-logon
   script (`setup.ps1.j2`) into a private directory under `/tmp`, packs them into a
   small ISO and uploads it to the libvirt pool. The answer file holds the account
   password, so it never touches the work tree and is deleted at the end;
2. creates the VM with `virt-install`: UEFI with Secure Boot and Microsoft keys,
   emulated TPM 2.0, SMM, SATA disk and e1000e NIC (in-box drivers, no virtio ISO),
   QXL display and a USB tablet, the evaluation ISO and the answer ISO as CD-ROMs;
3. presses Enter at the firmware's "boot from CD or DVD" prompt, for a few seconds
   only: later in Setup the Cancel button has the focus;
4. lets Setup run unattended: disk 0 wiped and partitioned (EFI, MSR, Windows),
   image 1 installed, computer name from the inventory host, Italian locale and
   keyboard, OOBE screens hidden, local administrator `ansible_user` with the
   inventory password, one automatic logon;
5. at that logon, `setup.ps1` installs OpenSSH Server, sets PowerShell as its
   default shell, opens port 22, turns off sleep and hibernation, clears the
   autologon password and moves the NIC to the static address. It logs to
   `C:\Windows\Temp\edulab-setup.log`;
6. waits for SSH at the inventory address, checks the script's outcome, reports
   when the evaluation ends, shuts Windows down, ejects the media and takes the
   `baseline` snapshot.

### Domain controller: `tests/vm_build_dc.yaml`

```bash
ansible-playbook tests/vm_build_dc.yaml                          # about 10 minutes
```

A Debian 13 netinst driven by a preseed (`tests/vm_build/preseed.cfg.j2`): static
address and host name from the inventory, `ansible_user` with sudo and the
inventory password (hashed with `openssl passwd -6`), no root password, SSH server,
`python3` and `qemu-guest-agent`. Virtio disk and NIC, so the interface is
`enp1s0`, the default of `samba_dc_build_ifname`.

After the installation the playbook prepares the two things `samba_dc_build`
expects and the Debian installer does not leave behind:

- the static configuration moves from `/etc/network/interfaces` to
  `/etc/network/interfaces.d/<iface>`, with the exact content the role writes
  there. Two stanzas for the same interface collide at the next `ifup`, which the
  role triggers with its reboot handler;
- `/etc/resolv.conf` names a nameserver, since the role's first `apt` task runs
  before it rewrites the resolver.

It then reboots once to prove the VM comes back with its address, shuts it down
and takes the `baseline` snapshot. The domain is provisioned by
`tests/samba_dc_build.yaml` or `tests/samba_dc.yaml`, which start from that
snapshot.

---

## The `baseline` snapshot

Every test playbook starts by reverting to a snapshot named `baseline`. The build
playbooks take it with the VM shut off: a clean OS with the inventory account and
SSH, no additional software.

> **Why the snapshot is taken with the VM shut off.** `virsh snapshot-revert`
> restores the state the snapshot was taken in, so a shut-off baseline leaves the
> domain shut off — which is precisely what the test playbooks expect: the next
> step sends a Wake-on-LAN packet, and `virsh_wakeonlan` turns it into a
> `virsh start`. The sequence is then the same one used against real
> workstations. If you prefer not to run the listener, revert manually with
> `virsh snapshot-revert <domain> baseline --running` or start the VM with
> `ansible-playbook tests/virsh.yaml -e vm=teacher -e cmd=start`.

Rebuild the VM rather than patching its baseline whenever the baseline itself
changes — a new Windows build, a different maintenance account — and in any case
when the evaluation period expires.

---

## Manual fallback

If an unattended build stops on a screen the answer file does not handle (a new
OOBE page in a future Windows release, for instance), look at the VM display
(`virt-viewer`, or `tools/vm/vmgui.py <host> shot`) and finish by hand:

### Windows

```bash
virt-install \
  --name win_edulab-teacher \
  --osinfo win11 \
  --memory 4096 --vcpus 2 --cpu host-passthrough \
  --machine q35 --features smm.state=on \
  --boot uefi,firmware.feature0.name=secure-boot,firmware.feature0.enabled=yes,firmware.feature1.name=enrolled-keys,firmware.feature1.enabled=yes \
  --tpm backend.type=emulator,backend.version=2.0,model=tpm-crb \
  --disk size=128,format=qcow2,bus=sata \
  --network network=default,mac=52:54:00:ed:1a:21,model=e1000e \
  --cdrom /path/to/Win11_Enterprise_Eval.iso \
  --graphics spice --video qxl --input tablet,bus=usb
```

1. At OOBE, the Enterprise evaluation still offers a local account: choose
   **Sign-in options** → **Domain join instead** instead of signing in with a
   Microsoft account, and name it after `ansible_user`, with the vault password.
2. Prepare the host for Ansible following
   [Preparing the Managed Hosts](installation.md#preparing-the-managed-hosts-windows-11-pro):
   OpenSSH Server, PowerShell as `DefaultShell`, firewall rule for port 22.
3. Set the static IP of the inventory, netmask `255.255.255.0`, gateway and DNS
   `192.168.122.1`, and the computer name.
4. Check from the control node with `ansible teacher -m ansible.windows.win_ping`,
   shut the VM down and take the snapshot:

   ```bash
   virsh snapshot-create-as win_edulab-teacher baseline \
        --description "clean Win11 Enterprise Eval + maint account + OpenSSH"
   ```

### Debian

Install from the netinst image with the defaults (SSH server, no desktop), the
`ansible_user` account with sudo and the static address of the inventory. Then
apply the two network fixes described above — static stanza in
`/etc/network/interfaces.d/enp1s0`, nameserver in `/etc/resolv.conf` — before
taking the shut-off `baseline` snapshot.
