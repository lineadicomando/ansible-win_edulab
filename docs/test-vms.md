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

The VMs live on the system libvirt instance (`qemu:///system`), because
`tests/virsh.yaml` runs `virsh` with `become: true`.

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
in `inventories/school/group_vars/all/vars.yaml`.

Addresses are **static inside each guest**: the inventory pins them below the
libvirt DHCP range (`.100`–`.200`), so nothing depends on a lease. The MAC
addresses matter as well — the `wol` role sends its magic packet to
`ansible_mac`, so the value in `hosts.yaml` must be the one on the VM NIC.

| Inventory host | VM name          | IP               | MAC                 |
|----------------|------------------|------------------|---------------------|
| `samba_ad_dc`  | `deb13-samba-dc` | `192.168.122.2`  | `52:54:00:38:64:a0` |
| `teacher`      | `win11-pc00`     | `192.168.122.10` | `52:54:00:1c:82:8e` |
| `student01`    | `win11-pc01`     | `192.168.122.11` | `52:54:00:a6:db:78` |
| `student02`    | `win11-pc02`     | `192.168.122.12` | `52:54:00:bf:d8:d6` |

The VM names are the ones `tests/virsh.yaml` maps in its internal `vm_map`;
choosing different names means editing that map, and different MACs or IPs mean
editing `inventories/school/hosts.yaml`.

---

## Creating a Windows test VM

```bash
sudo virt-install \
  --name win11-pc00 \
  --osinfo win11 \
  --memory 4096 --vcpus 2 --cpu host-passthrough \
  --machine q35 --boot uefi,loader.secure=yes --features smm.state=on \
  --tpm backend.type=emulator,backend.version=2.0,model=tpm-crb \
  --disk size=128,format=qcow2,bus=sata \
  --network network=default,mac=52:54:00:1c:82:8e,model=e1000e \
  --cdrom /path/to/Win11_Enterprise_Eval.iso \
  --graphics spice
```

- **Secure Boot and TPM 2.0** are hard requirements of the Windows 11 installer;
  without them setup stops on a compatibility screen.
- **SATA disk and e1000e NIC** are used so that Windows setup finds disk and
  network with its in-box drivers, without a virtio driver ISO. Virtio is faster
  but not worth the extra step for a test VM.
- The 128 GiB disk is thin-provisioned: a clean baseline occupies around 20 GiB.

### Windows setup inside the VM

1. At OOBE, the Enterprise evaluation still offers a local account: choose
   **Sign-in options** → **Domain join instead** instead of signing in with a
   Microsoft account.
2. Set the static IP, netmask `255.255.255.0`, gateway and DNS `192.168.122.1`
   as per the table above.
3. Prepare the host for Ansible following
   [Preparing the Managed Hosts](installation.md#preparing-the-managed-hosts-windows-11-pro):
   the `maint` administrative account with the password stored in the vault,
   OpenSSH Server, PowerShell as `DefaultShell`, firewall rule for port 22.
4. Check the result from the control node:

   ```bash
   ansible teacher -m ansible.windows.win_ping
   ```

The other two workstations can be installed the same way, or cloned once the
first one is ready:

```bash
sudo virt-clone --original win11-pc00 --name win11-pc01 \
                --mac 52:54:00:a6:db:78 --auto-clone
```

After cloning, boot the clone and change its computer name and static IP —
duplicated names are a nuisance once the machines join the domain.

---

## The `baseline` snapshot

Every test playbook starts by reverting to a snapshot named `baseline`, so each
test VM must have one. It represents a clean Windows installation with SSH
working and no additional software:

```bash
sudo virsh shutdown win11-pc00
# wait for the VM to be shut off, then:
sudo virsh snapshot-create-as win11-pc00 baseline \
     --description "clean Win11 Enterprise Eval + maint account + OpenSSH"
```

```bash
sudo virsh snapshot-list win11-pc00     # check it exists
```

> **Why the snapshot is taken with the VM shut off.** `virsh snapshot-revert`
> restores the state the snapshot was taken in, so a shut-off baseline leaves the
> domain shut off — which is precisely what the test playbooks expect: the next
> step sends a Wake-on-LAN packet, and `virsh_wakeonlan` turns it into a
> `virsh start`. The sequence is then the same one used against real
> workstations. If you prefer not to run the listener, revert manually with
> `sudo virsh snapshot-revert win11-pc00 baseline --running` or start the VM with
> `ansible-playbook tests/virsh.yaml -e vm=teacher -e cmd=start`.

Rebuild the snapshot whenever the baseline itself changes — a new Windows build,
a different maintenance account — and in any case when the evaluation period
expires and the VM is rebuilt from a fresh ISO.

---

## The Debian DC VM

The Domain Controller VM is installed from the Debian netinst image with the
usual defaults (SSH server, no desktop), the static address `192.168.122.2`, and
the same `maint` account with sudo rights. From there,
`playbooks/samba_dc_build.yaml` provisions the domain; the `samba_dc_build_*`
variables are described in [Installation](installation.md#6-configure-samba-dc-parameters-optional).

A `baseline` snapshot taken right after the OS install — before provisioning —
makes `tests/samba_dc_build.yaml` repeatable.

> **Two things to settle before that snapshot.** `samba_dc_build` assumes the
> machine already resolves names: its first `apt` task runs before the role
> rewrites `/etc/resolv.conf`, so an installer leftover with no `nameserver`
> line fails the build immediately. And the static address must *not* be written
> as an `iface` stanza in `/etc/network/interfaces`: the role writes its own into
> `/etc/network/interfaces.d/`, and two stanzas for the same interface collide at
> the next `ifup` — which the role triggers with its reboot handler. Put the
> static configuration in `/etc/network/interfaces.d/<iface>` instead, with the
> same content the role writes there, and leave the main file with its stanza
> commented out: the VM then boots with its address both before and after the
> role runs, and the role's own task reports no change.
