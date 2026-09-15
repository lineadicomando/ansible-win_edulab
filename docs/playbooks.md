# Available Playbooks

Playbooks that target a specific group accept the `-e target_hosts=<group|host>` parameter to override the default target. Using the `-l` flag allows you to narrow down the target even further.

| Playbook | Default target |
|---|---|
| `samba_dc_build.yaml` | `samba_ad_dc` |
| `samba_dc_join.yaml` | `lab_win` |
| `win_wm.yaml` | `all` — always pass `-l` |
| `lab_cad.yaml` | `lab_cad` |
| `lab_coding.yaml` | `lab_coding` |
| `veyon.yaml` | `lab_win` |
| `maintenance.yaml` | `windows11` |
| `autologon.yaml` | `lab_win` |
| `wol.yaml` | `lab_win` |
| `shutdown.yaml` | `lab_win` |
| `gcpw.yaml` | `lab_win` |
| `seb_classroom.yaml` | `students` |

---

### `samba_dc_build.yaml` — Provision the Samba AD DC

Builds a full Samba 4 Active Directory Domain Controller on a Debian host:
network configuration, firewall (nftables), Kerberos, NTP (chrony), Cockpit.
The role is idempotent: reruns skip the `samba-tool domain provision` step.

```bash
ansible-playbook playbooks/samba_dc_build.yaml
```

### `samba_dc_join.yaml` — Join Windows hosts to the domain

Joins Windows 11 workstations to the Samba AD domain.

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
ansible-playbook playbooks/win_wm.yaml -l lab_win -e "t=chrome,python314"

# Uninstall Firefox
ansible-playbook playbooks/win_wm.yaml -l lab_win -e "t=firefox-off"

# Windows Update, then restart
ansible-playbook playbooks/win_wm.yaml -l lab_win -e "t=wu-run,restart"

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
maintenance notice, then runs CHKDSK, the WIM component store check, SFC and
disk optimization. A second play unlocks the workstations and restarts them.

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
