# Installation and Initial Setup

This guide outlines the requirements and steps necessary to configure an EduLab environment and begin managing it via Ansible.

## Requirements

### Control node

The reference control node is a **Linux** machine — the project is developed and
run on Debian 13 and Fedora, and any current distribution is suitable. A Windows
control node is supported through WSL2 for compatibility, but it is not the
platform the project targets: see
[Preparing the Control Node](#preparing-the-control-node).

- **Linux** (Debian 13, Fedora, or an equivalent current distribution)
- **Ansible** >= 2.20 (the win_workman roles declare `min_ansible_version: "2.20"`)
- **Git**
- **Python** >= 3.11 (only required for the MCP servers)
- **sshpass**, when the managed hosts are reached with password authentication
- An **SSH key** for connecting to the managed hosts (see `inventories/school/group_vars/all/vars.yaml`)
- **QEMU/KVM with libvirt** — recommended, and required to run the test playbooks
  in `tests/`, which drive the test VMs locally via `virsh`

### Managed hosts

- **Windows 11 Pro** (see below for preparation)
- **Debian 13** for the Domain Controller (if applicable)

---

## Preparing the Control Node

The *Control Node* is the machine Ansible commands are run from. This project
assumes it runs **Linux**, which is also where the MCP servers and the QEMU/KVM
test VMs live. The WSL2 path documented afterwards exists only so the project
can be used where the control node has to be a Windows machine.

### Linux (reference platform)

#### 1. Install the base packages

Debian / Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv sshpass
```

Fedora:

```bash
sudo dnf install -y git python3 python3-pip sshpass
```

#### 2. Install Ansible >= 2.20

The version required here is newer than the one packaged by most distributions,
so install Ansible from PyPI — `pipx` keeps it isolated from the system Python:

```bash
sudo apt install -y pipx      # Debian/Ubuntu
sudo dnf install -y pipx      # Fedora

pipx install --include-deps ansible
```

Check that the result satisfies the requirement:

```bash
ansible --version   # must report core 2.20 or newer
```

#### 3. Install QEMU/KVM for the test VMs (recommended)

The playbooks in `tests/` revert and start the lab VMs on the control node
itself through `virsh` (see `tests/virsh.yaml` and
[`tests/README.md`](../tests/README.md)), so a libvirt/QEMU host is what the
test workflow is built around.

Debian / Ubuntu:

```bash
sudo apt install -y qemu-system-x86 libvirt-daemon-system libvirt-clients virt-manager
```

Fedora:

```bash
sudo dnf install -y @virtualization virt-manager
```

Then enable the daemon and grant the current user access to the system libvirt
instance (log out and back in for the group to take effect):

```bash
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt "$USER"
```

The test playbooks wake their targets with Wake-on-LAN, like they do with real
workstations, so the host also runs
[`virsh_wakeonlan`](https://github.com/lineadicomando/virsh_wakeonlan) — a
systemd listener that turns the magic packet into a `virsh start` on the
matching domain.

The VM names and the `baseline` snapshot expected by the test playbooks are
documented in [`tests/README.md`](../tests/README.md), while
[Test VMs (QEMU/KVM)](test-vms.md) walks through building them from scratch —
including where to download the Windows evaluation ISO and the licence terms
that come with it.

### Windows 11 via WSL2 (compatibility)

> **Note:** this path is provided for compatibility, not as the recommended
> setup. Ansible has no native Windows control node, so it runs inside a Linux
> distribution under WSL2 anyway; on top of that, the QEMU/KVM test
> environment in `tests/` is not available from WSL2, so the test playbooks
> cannot be used from a Windows control node.

If the computer you intend to run Ansible commands from is a Windows 11 machine, the most reliable way to run Ansible is via **WSL2** (Windows Subsystem for Linux).

#### 1. Install WSL2 and Ubuntu

Open PowerShell as an Administrator and run:
```powershell
wsl --install
```
This command will enable the necessary features and install the default Ubuntu distribution. When it finishes, restart your computer if prompted by the system.

#### 2. Configure the Linux environment

Once restarted, open the **Ubuntu** app from the Start menu and complete the initial setup by creating a UNIX username and password. After that, update the system and install the required packages:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3-pip python3-venv sshpass pipx
pipx install --include-deps ansible
```

Ansible is installed with `pipx` here for the same reason as on a Linux control
node: the `ansible` package shipped by the distribution is usually older than
the 2.20 required by the roles.

From this point on, you can clone the repository and run playbooks directly from the Ubuntu terminal.

> **Performance tip:** Ensure you clone the repository inside the native Linux file system (for example, in your home `~/Projects/`) and not on the Windows drive (under `/mnt/c/`). Linux file operations are significantly faster if they stay within the WSL2 virtual disk.

---

## Preparing the Managed Hosts (Windows 11 Pro)

To allow Ansible to manage the Windows 11 Pro workstations, the operating system must be prepared by enabling remote access and creating a maintenance user.

### 1. Create the local administrative account

Create a local account named `maint` (or a name of your choice) that Ansible will use to connect and execute operations:
1. Open **Settings** > **Accounts** > **Other users**.
2. Add a new local account without using a Microsoft account.
3. Assign the **Administrator** account type to the new user.

> **Note:** This account's password will be the same one configured in the `vault.yaml` file (see the *Getting Started* section).

### 2. Install and configure OpenSSH Server

Ansible connects to Windows via SSH using PowerShell as the remote shell.

1. Open **Settings** > **System** > **Optional features**.
2. Click on **View features**, search for "OpenSSH Server" and install it.
3. Open **Services** (`services.msc`), search for **OpenSSH SSH Server**.
4. Set the startup type to **Automatic** and start the service.

Alternatively, from a PowerShell terminal (Run as Administrator):

```powershell
# Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# Start the service
Start-Service sshd

# Configure automatic startup
Set-Service -Name sshd -StartupType 'Automatic'
```

### 3. Set PowerShell as the default shell for SSH

Run this command in PowerShell (as Administrator) to instruct the OpenSSH server to use PowerShell instead of the command prompt (`cmd.exe`) when Ansible connects:

```powershell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
```

### 4. Configure the Firewall

Ensure that port 22 (SSH) is open in the Windows firewall. The OpenSSH installation should have already created a rule named "OpenSSH SSH Server (sshd)".

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/lineadicomando/ansible-win_edulab.git
cd ansible-win_edulab
```

### 2. Create the vault password file

`ansible.cfg` reads the vault password from `.ansible-vault-pass.txt` (gitignored):

```bash
$EDITOR .ansible-vault-pass.txt
chmod 600 .ansible-vault-pass.txt
```

### 3. Create and encrypt the vault file

Copy the provided template to define the credentials:

```bash
cp inventories/school/group_vars/all/vault.yaml.example \
   inventories/school/group_vars/all/vault.yaml

# Edit vault.yaml with the real credentials (e.g., the "maint" user), then encrypt it:
ansible-vault encrypt inventories/school/group_vars/all/vault.yaml

# To edit the vault later:
ansible-vault edit inventories/school/group_vars/all/vault.yaml
```

Variables in `vault.yaml`:

| Variable | Description |
|---|---|
| `ansible_vault_password` | SSH password for the `maint` user |
| `ansible_vault_become_password` | sudo password (usually the same as the SSH password) |
| `samba_dc_build_administrator_passwd` | Domain administrator password (must meet AD complexity requirements: minimum 7 characters) |

### 4. Install Ansible collections

```bash
ansible-galaxy collection install -r requirements.yaml -p .
```

Collections are installed from the `main` branch of their respective Git repositories into `./ansible_collections/` (gitignored).

### 5. Customize the inventory

Edit `inventories/school/hosts.yaml` with the actual addresses of the machines in your lab. The group names matter, as each playbook is associated with a specific default group.

```yaml
all:
  children:
    servers:
      hosts:
        samba_ad_dc:
          ansible_host: <DC-IP>
          ansible_mac: <DC-MAC>
    teachers:
      hosts:
        teacher:
          ansible_host: <teacher-IP>
          ansible_mac: <teacher-MAC>     # used by Wake-on-LAN
    students:
      hosts:
        student01:
          ansible_host: <student1-IP>
          ansible_mac: <student1-MAC>
        student02:
          ansible_host: <student2-IP>
          ansible_mac: <student2-MAC>
    lab_win:         # default target for many playbooks
      hosts: { teacher:, student01:, student02: }
    windows11:       # SSH/PowerShell connection settings
      hosts: { teacher:, student01:, student02: }
    # ... other custom groups (e.g., lab_cad, lab_coding)
```

Also, edit `inventories/school/group_vars/all/vars.yaml` to define the SSH key path and collection-level settings.

> **Security Note:** The default configuration in `ansible_ssh_common_args` disables host key verification to ease use in an isolated lab network. The same file indicates the strict alternative for non-isolated environments.

### 6. Configure Samba DC parameters (Optional)

If you plan to install a Samba Domain Controller, edit the `samba_dc_build_*` variables in `inventories/school/group_vars/all/vars.yaml`:

```yaml
samba_dc_build_realm: SCHOOL.INTERNAL        # Kerberos realm (uppercase)
samba_dc_build_domain: SCHOOL                # NetBIOS domain name
samba_dc_build_fqdn: dc.school.internal
samba_dc_build_search_domain: school.internal
samba_dc_build_nameserver: 127.0.0.1         # DC is its own DNS server
samba_dc_build_address: 192.168.122.2        # Static IP of the DC
samba_dc_build_netmask: 255.255.255.0
samba_dc_build_gateway: 192.168.122.1
samba_dc_build_ifname: enp1s0                # Network interface name
samba_dc_build_ntp_server: 192.168.122.1     # Upstream NTP server
samba_dc_build_ntp_allow_network: 192.168.122.0/24
samba_dc_build_administrator_username: admin
```

---

## Updating Collections

Since `ansible-galaxy` does not reinstall a collection if it is already present, updating repositories from Git sources requires forcing the operation with the `--force` flag:

```bash
ansible-galaxy collection install -r requirements.yaml -p . --force
```
