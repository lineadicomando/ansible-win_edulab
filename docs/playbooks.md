# Available Playbooks

Playbooks that target a specific group accept the `-e target_hosts=<group|host>` parameter to override the default target. Using the `-l` flag allows you to narrow down the target even further.

| Playbook | Default target |
|---|---|
| `samba_dc_build.yaml` | `samba_dc` |
| `samba_dc_join.yaml` | `win_managed` |
| `win_wm.yaml` | `all` — always pass `-l` |
| `lab_cad.yaml` | `lab_cad` |
| `lab_coding.yaml` | `lab_coding` |
| `veyon.yaml` | `win_managed` |
| `maintenance.yaml` | `win_managed` |
| `autologon.yaml` | `win_managed` |
| `wol.yaml` | `win_managed` |
| `shutdown.yaml` | `win_managed` |
| `gcpw.yaml` | `win_managed` |
| `seb_classroom.yaml` | `students` |
| `win_iso_build.yaml` | `localhost`, or `win_iso_host` — builds a file on the controller |

---

### `samba_dc_build.yaml` — Provision the Samba AD DC

Builds a full Samba 4 Active Directory Domain Controller on a Debian host:
network configuration, firewall (nftables), Kerberos, NTP (chrony), Cockpit.
The role is idempotent: reruns skip the `samba-tool domain provision` step.

```bash
ansible-playbook playbooks/samba_dc_build.yaml
```

### `samba_dc_join.yaml` — Join Windows hosts to the domain

Joins Windows 11 workstations to the Samba AD domain, through the `domain`
role of `lineadicomando.win_workman` (task `domain-join`): it points the
clients' DNS at the DC, then joins. Variables: `win_workman_domain_*` in
`group_vars/all`.

```bash
ansible-playbook playbooks/samba_dc_join.yaml
```

### `win_wm.yaml` — Windows software and system management

Installs, uninstalls, or manages software and settings on Windows 11
workstations. Pass tasks via the `-e t=` parameter.

This playbook imports `lineadicomando.win_workman.win_workman`, which runs on
`hosts: all` and ignores `target_hosts`: **always limit it with `-l`**, or it
will also try to run Windows tasks against the domain controller.

```bash
# Install Chrome and Python 3.14
ansible-playbook playbooks/win_wm.yaml -l win_managed -e "t=chrome,python314"

# Uninstall Firefox
ansible-playbook playbooks/win_wm.yaml -l win_managed -e "t=firefox-off"

# Windows Update, then restart
ansible-playbook playbooks/win_wm.yaml -l win_managed -e "t=wu-run,restart"

# Target a single host
ansible-playbook playbooks/win_wm.yaml -l teacher -e "t=chrome"
```

Task format: `<software>[-<action>]` — default action is `on` (install).
Common actions: `on`, `off`, `download`, `info`.

Available tasks include: `chrome`, `firefox`, `edge`, `brave`, `libreoffice`,
`gimp`, `inkscape`, `vscode`, `python310`–`python314`, `zoom`, `veyon`,
`wu-run`, `wu-pause`, `restart`, `shutdown`, `lock-on`, `lock-off`,
`wallpaper`, … — the full catalogue is the `roles/` directory of the
win_workman collection, or the `get_role_info` MCP tool.

### `lab_cad.yaml` — CAD lab packages

Installs the CAD lab software set: LibreOffice, Chrome, SketchUp 2026,
AutoCAD LT 2026, TinyCAD.

```bash
ansible-playbook playbooks/lab_cad.yaml
```

### `lab_coding.yaml` — Coding lab packages

Installs the coding lab software set: LibreOffice, Chrome, Edge, Firefox,
Brave, GIMP, Inkscape, ntop, 7-Zip, PureData, Postman, VS Code, Python 3.14,
Embarcadero Dev-C++.

```bash
ansible-playbook playbooks/lab_coding.yaml
```

### `veyon.yaml` — Veyon classroom management

Installs and configures Veyon on all lab workstations. Teachers are
configured as Veyon masters, students as clients (`win_workman_veyon_master`
in `group_vars/teachers` and `group_vars/students`).

```bash
ansible-playbook playbooks/veyon.yaml
```

### `maintenance.yaml` — Routine maintenance

Wakes the workstations, logs users off and locks the logon screen with a
maintenance notice, restarts those with a reboot pending, then runs CHKDSK,
the component store scan (DISM ScanHealth), SFC and disk optimization. It does
not run Windows Update.

The unlock and the final restart run whatever the checks find: a workstation
that fails one of them skips the checks after it and shows as failed in the
recap, but is not left locked. Only a host that becomes unreachable half-way
stays locked; `lock-off` through `win_wm.yaml` unlocks it once it is back.

```bash
ansible-playbook playbooks/maintenance.yaml
```

### `autologon.yaml` — Windows autologon

Configures Windows autologon on lab workstations and restarts them.

```bash
ansible-playbook playbooks/autologon.yaml
```

### `wol.yaml` — Wake on LAN

Sends a Wake-on-LAN magic packet to the target hosts, using their `ansible_mac`.

```bash
ansible-playbook playbooks/wol.yaml
```

### `shutdown.yaml` — Shut down workstations

```bash
ansible-playbook playbooks/shutdown.yaml
```

### `gcpw.yaml` — Google Credential Provider for Windows

Installs GCPW, so users can log on to the workstations with their Google
Workspace account. Set `win_workman_gcpw_domains_allowed_to_login` to the
allowed domain(s).

```bash
ansible-playbook playbooks/gcpw.yaml -e win_workman_gcpw_domains_allowed_to_login=school.edu
```

### `seb_classroom.yaml` — Safe Exam Browser for Google Classroom

Installs and deploys Safe Exam Browser pre-configured for Google Classroom,
with URL filtering that allows Google domains and blocks Gemini and NotebookLM.

```bash
ansible-playbook playbooks/seb_classroom.yaml
# Override the Google Workspace domain for the account chooser
ansible-playbook playbooks/seb_classroom.yaml -e win_workman_seb_account_chooser=school.edu
```

### `win_iso_build.yaml` — Windows installation ISO ready for Ansible

Wrapper of the `win_iso` role of win_workman (its doc,
`docs/roles/management/win_iso.md` in the collection, covers every variable).
From a Microsoft ISO put by hand in `/srv/ansible/storage/win_iso`, it builds an
ISO that installs unattended, keeps only Home, Pro, Education and Pro Education,
creates the local administrator of the inventory (`ansible_user`,
`ansible_password` from the vault) and has OpenSSH Server answering from the
first boot, with PowerShell as its shell and port 22 open. It also lifts the
TPM, Secure Boot and RAM checks and turns off automatic BitLocker encryption.
The output is `<name>-unattended.iso` next to the source.

OpenSSH Server comes either from the Win32-OpenSSH MSI installed during Setup
(`msi`, the default: only the controller is involved, but Windows Update does
not update it) or as the Windows capability integrated by DISM on a Windows host
(`dism`: needs the Languages and Optional Features ISO in the same folder and
about 40 GB free on the host; Windows Update keeps it updated).

```bash
# MSI, credentials of the group all of the school inventory
ansible-playbook playbooks/win_iso_build.yaml \
  -e win_workman_win_iso_source=Windows11_Client_x64_it-it_26300_9457.iso
# DISM on the teacher VM; credentials of teacher
ansible-playbook playbooks/win_iso_build.yaml -e win_iso_host=teacher -e win_workman_win_iso_ssh=dism \
  -e win_workman_win_iso_source=Windows11_Client_x64_it-it_26300_9457.iso \
  -e win_workman_win_iso_fod_source=26100.1.240331-1435.ge_release_amd64fre_CLIENT_LOF_PACKAGES_OEM.iso
# The editions of an ISO, without building anything
ansible-playbook playbooks/win_iso_build.yaml -e win_iso_action=info -e win_workman_win_iso_source=<iso>
```

Through MCP the role runs as any win_workman task: `run_tasks(l=<host>,
t=["win_iso-build"] or ["win_iso-build-dism"], extra_vars={...}, background=true)`;
the host gives the credentials, so a host of another inventory makes the ISO of
that lab, and with `msi` it may be off.

`win_workman_win_iso_wipe_disk=true` erases disk 0 without asking: then a PC that
boots from a forgotten stick reinstalls itself. Write the ISO to a stick with
Rufus, leaving its customisations unticked, or copy it to a Ventoy stick. The ISO
holds the account password in clear: keep it, and the sticks, safe.
