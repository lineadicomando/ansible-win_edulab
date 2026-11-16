# Available Playbooks

Each playbook in `playbooks/` does one thing, so that it can be a step of a
cockpit-fleet workflow, and runs the same from the command line and through
the `run_playbook` MCP tool.
`maintenance.yaml` is the exception: it chains a whole maintenance in one run,
for the command line.

```bash
ansible-playbook playbooks/<name>.yaml [-i inventories/<lab>/hosts.yaml] [-l <host|group>] [-e target_hosts=<group>]
```

## Conventions

**Target.** A playbook runs on `win_managed` (`lab_win` in an inventory that
still has the old name) unless its header names another group. `-e
target_hosts=<group|host>` replaces it, `-l` narrows it, as does the limit of a
cockpit-fleet template. Inside a workflow, a step runs on the hosts the step
before it passed on (`wf_hosts`).

**One step, one shared body.** Every playbook imports
`playbooks/tasks/wf_step.yaml`, which wraps its win_workman tasks:

1. a gate waits up to `wf_connect_timeout` seconds (30) for each host; one that
   does not answer is set aside as unreachable;
2. the tasks run in a block whose rescue records a host that fails, so that the
   other hosts carry on;
3. `set_stats` (`per_host: false`) passes on what the next steps need;
4. unless `wf_tolerant` is true, the hosts that did not complete the step fail
   at the end: a run by hand fails as it always did, with the reason in the
   output.

**Tolerant steps.** With `wf_tolerant: true` a step succeeds even when hosts
fail or are switched off, so one broken PC out of thirty does not stop the
maintenance of the others. Set it on every template used as a workflow step
(in its variables, or in a variable set they share), and end the workflow with
`wf_report.yaml`, which fails if any host failed along the way.

**What steps pass on.** Names start with `wf_`, because what a step passes on
wins over the survey of the next one:

| Variable | Content |
|---|---|
| `wf_hosts` | hosts that completed the last step; the next step runs on them only |
| `wf_unreachable` | hosts that never answered, over all the steps |
| `wf_failed` | `{host: "step: reason"}`, over all the steps |
| `wf_locked` | hosts in maintenance mode: added by `maint_lock`, removed by `maint_unlock` |
| `wf_wu_scan`, `wf_wu_report`, `wf_sysinfo` | per-host reports of `wu_scan`, `wu_run`/`wu_optional`, `sysinfo` |

`set_stats` only travels between the steps of a workflow: plays chained with
`import_playbook` in one run (as in `tests/`) do not see it.

**Survey.** The header of each playbook lists the variables worth asking at
launch, with type and default. A survey answer is text, a number, a choice or a
yes/no: list variables (`win_workman_chkdsk_volumes`) go in the inventory or in
the template's variables. Where a playbook builds a task string from an answer
(`wu_profile`, `wu_pause_for`, `restart_when`) it checks it first and stops on a
value it does not know.

**A host lost half-way.** A host that answers the gate and then drops its
connection during a task cannot be rescued (Ansible hands no unreachable host
to a rescue): it is recorded in `wf_failed` and the step fails with exit code
4. `maint_unlock`, linked with "always", still unlocks it once it is back.

## Catalogue

| Playbook | win_workman tasks | Survey |
|---|---|---|
| **Power and reachability** | | |
| `wol.yaml` | `wol`, then the gate | `win_workman_wol_timeout`, `wf_connect_timeout` |
| `maint_restart.yaml` | `restart` or `restart-if-pending` | `restart_when` (always, pending) |
| `shutdown.yaml` | `shutdown` | |
| **Maintenance** | | |
| `maint_lock.yaml` | `lock` | `win_workman_mode_title`, `_text`, `_force_logoff` |
| `maint_unlock.yaml` | `lock-off`, on `wf_locked` | `wf_connect_timeout` |
| `maint_chkdsk.yaml` | `chkdsk` | |
| `maint_wim_scan.yaml` | `wim-scan` | `win_workman_wim_scan_fail_on_repairable` |
| `maint_wim_repair.yaml` | `wim-repair` | `win_workman_wim_repair_source`, `_limit_access` |
| `maint_sfc.yaml` | `sfc` | `win_workman_restart` |
| `maint_optimize.yaml` | `optimize` | `win_workman_optimize_defrag` |
| `maintenance.yaml` | all of the above, in one run | |
| **Windows Update** | | |
| `wu_scan.yaml` | `wu-scan` | |
| `wu_run.yaml` | `wu-run-<profile>` | `wu_profile` (security, full, upgrades, cat-…), `win_workman_wu_unpause`, … |
| `wu_optional.yaml` | `wu-run-optional-<categories>` | `wu_categories` (upgrades, updates, drivers) |
| `wu_pause.yaml` | `wu-max_pause_days-…`, `wu-pause-…` | `wu_pause_for`, `wu_max_pause_days` |
| `wu_resume.yaml` | `wu-resume` | |
| `wu_sync_ui.yaml` | `wu-sync_ui` | |
| **Information** | | |
| `sysinfo.yaml` | `sysinfo-on[-<sections>]` | `sysinfo_sections`, `sysinfo_publish` |
| `wf_report.yaml` | none: reads what the steps passed on | `wf_fail_on_unreachable` |
| **Software and configuration** | | |
| `software.yaml` | the survey's list, or `win_edulab_software` | `software` |
| `win_wm.yaml` | any task strings | `t` |
| `lab_cad.yaml`, `lab_coding.yaml` | example package sets (default groups `lab_cad`, `lab_coding`) | |
| `veyon.yaml` | `veyon`, `veyon-config` | |
| `domain_join.yaml` | `domain-join` | |
| `gcpw.yaml` | `gcpw` | |
| `autologon.yaml` | `autologon` | `win_workman_autologon_restart` |
| `seb_classroom.yaml` | `seb`, `seb-deploy` (default group `students`) | `win_workman_seb_account_chooser` |
| `win_iso_build.yaml` | `win_iso` role, on `localhost` or `win_iso_host` | |

`wu-reset` has no playbook on purpose: the role keeps it for a host stuck by
hand, through `run_tasks`.

## Workflows for cockpit-fleet

One job template per playbook, with `wf_tolerant: true` in its variables and
the survey of its header; the steps below are linked "on success" unless
marked. `wf_report` has no limit (it runs on `localhost`).

**Monthly maintenance**

```
wol → maint_lock → maint_restart (pending) → maint_chkdsk → maint_wim_scan → maint_sfc → maint_optimize
                                                                                              │
      maint_unlock ◀── always ─────────────────────────────────────────────────────────────────┘
          │ always
      maint_restart (always) ── always ──▶ wf_report
```

**Security updates**

```
wol → sysinfo (os) → wu_scan → maint_lock → wu_run (security)
                                               │ always
                                        maint_unlock → wu_pause (1-m) → sysinfo (os) ─ always ─▶ wf_report
```

With updates paused between runs, give `wu_run` `win_workman_wu_unpause: true`.

**Next Windows release (feature update offered as optional)**

```
wol → sysinfo (os-security-wu) → maint_lock → wu_optional (upgrades) → wu_run (security)
                                                                         │ always
                                                   maint_unlock ─ always ─▶ sysinfo (os) ─ always ─▶ wf_report
```

**Component store repair**, with an approval before the long step:

```
wol → maint_wim_scan (fail_on_repairable: false) → [approval] maint_wim_repair → maint_sfc ─ always ─▶ wf_report
```

Every step after `maint_lock` that can fail should reach `maint_unlock` through
an "always" link, directly or through the steps after it: a workflow that stops
on a failure starts nothing more, and only a step linked for it runs.

---

### `wol.yaml` — Wake on LAN

Sends the magic packet to the hosts with `ansible_mac` (through the `wol` role
directly, since the dispatcher needs the host awake to set its remote temporary
directory) and waits until they answer. A host without `ansible_mac`, such as
a laptop on Wi-Fi, is only waited for.

```bash
ansible-playbook playbooks/wol.yaml
```

### `win_wm.yaml` — any win_workman task

Runs the task strings given in `t`, on `win_managed` unless `target_hosts` or
`-l` say otherwise. A `wol` in the list wakes the hosts first, wherever it is.
The `run_tasks` MCP tool does not use it: it calls the collection's playbook.

```bash
ansible-playbook playbooks/win_wm.yaml -l teacher -e "t=wol,chrome,python314"
ansible-playbook playbooks/win_wm.yaml -e "t=firefox-off"
```

Task format: `<software>[-<action>]` — default action is `on` (install). The
full catalogue is the `roles/` directory of the win_workman collection, or the
`get_role_info` MCP tool. A template with a survey on `t` hands an operator
every action of the collection: keep it for administrators.

### `software.yaml` — the software set of a lab

Installs the task strings of the survey's `software` (comma-separated), or
else `win_edulab_software` from the inventory, so that one template serves
every lab:

```yaml
# inventories/<lab>/group_vars/students/vars.yaml
win_edulab_software: [libreoffice, chrome, vscode, python314]
```

Ansible does not merge lists: a host in two groups that both set it gets one of
the two.

### `maintenance.yaml` — Routine maintenance in one run

Wakes the workstations, logs users off and locks the logon screen with a
maintenance notice, restarts those with a reboot pending, then runs CHKDSK,
the component store scan (DISM ScanHealth), SFC and disk optimization. It does
not run Windows Update.

The unlock and the final restart run whatever the checks find: a workstation
that fails one of them skips the checks after it and shows as failed in the
recap, but is not left locked. Only a host that becomes unreachable half-way
stays locked; `maint_unlock.yaml` unlocks it once it is back.

```bash
ansible-playbook playbooks/maintenance.yaml
```

### `wu_run.yaml` and the other Windows Update steps

```bash
ansible-playbook playbooks/wu_scan.yaml -l students
ansible-playbook playbooks/wu_run.yaml -e wu_profile=full
ansible-playbook playbooks/wu_optional.yaml -l student01 -e wu_categories=upgrades
ansible-playbook playbooks/wu_pause.yaml -e wu_pause_for=2-m -e wu_max_pause_days=2-m
```

The notes of the `wu` role (`get_role_info("wu")`) explain why the optional
updates need their own step and why `TargetReleaseVersion` does not help.

### `domain_join.yaml` — Join Windows hosts to the domain

Joins Windows 11 workstations to an Active Directory domain, through the
`domain` role of `lineadicomando.win_workman` (task `domain-join`): it points
the clients' DNS at the domain controllers, then joins. Any AD DC will do
(Samba, Windows Server, an existing school domain): this project does not
build or manage it. Variables: `win_workman_domain_*` in `group_vars/all`.

### `veyon.yaml` — Veyon classroom management

Installs and configures Veyon on all lab workstations. Teachers are
configured as Veyon masters, students as clients (`win_workman_veyon_master`
in `group_vars/teachers` and `group_vars/students`).

### `autologon.yaml` — Windows autologon

Configures Windows autologon on lab workstations and restarts them
(`-e win_workman_autologon_restart=false` to skip the restart).

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
