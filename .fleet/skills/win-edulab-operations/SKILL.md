---
name: win-edulab-operations
description: Operating the Windows PCs of school labs with the playbooks of
  ansible-win_edulab - waking them, installing software, Windows Update,
  maintenance (lock, chkdsk, sfc, DISM, optimize, unlock), Veyon, shutdown -
  as job templates and workflows of Fleet. Read it before launching any of
  them, or to choose which one does what is asked.
---

# Operating the labs

Every playbook of `playbooks/` does one thing on the Windows PCs of an
inventory (a lab), so that it can be a job template of its own or a step of a
workflow. A template's description names its playbook: match the work to the
playbook below, then to the template that runs it on the inventory wanted
(one template may run on several inventories, chosen at launch).

## The playbooks

| Playbook | Does | Asks at launch |
|---|---|---|
| **Power** | | |
| `wol.yaml` | wakes the PCs (Wake-on-LAN) and waits until they answer | `win_workman_wol_timeout` |
| `maint_restart.yaml` | restarts them, always or only those with a reboot pending | `restart_when` (always, pending) |
| `shutdown.yaml` | shuts them down and waits until they are off | |
| **Maintenance** | | |
| `maint_lock.yaml` | maintenance mode: logs users off, logons restricted, a notice on the logon screen | title, text, force logoff |
| `maint_unlock.yaml` | gives back what `maint_lock` saved | |
| `maint_chkdsk.yaml` | online disk check, no restart | |
| `maint_wim_scan.yaml` | DISM /ScanHealth of the component store | fail on repairable |
| `maint_wim_repair.yaml` | DISM /RestoreHealth: long, up to an hour a PC | source |
| `maint_sfc.yaml` | sfc /scannow | restart first |
| `maint_optimize.yaml` | what Windows does by media type: retrim on SSDs, analysis *and* defragmentation on HDDs (long); there is no analysis alone | `win_workman_optimize_defrag`: defragment SSDs too (not recommended); false does not spare HDDs |
| **Windows Update** | | |
| `wu_scan.yaml` | lists the updates offered, changes nothing | |
| `wu_run.yaml` | installs updates of a profile: security, full, upgrades | `wu_profile` |
| `wu_optional.yaml` | the optional ones: feature update, preview cumulative, drivers | `wu_categories` |
| `wu_pause.yaml`, `wu_resume.yaml` | pause or resume Windows Update | `wu_pause_for` |
| **Information** | | |
| `sysinfo.yaml` | edition, build, hardware, disks, network, update state; changes nothing | sections |
| `wf_report.yaml` | the last step of a workflow: says which PCs failed along the way | |
| **Software and configuration** | | |
| `software.yaml` | installs or removes software: the list asked, or the lab's own `win_edulab_software` | `software` |
| `win_wm.yaml` | any task strings of win_workman (skill win-workman of the collection) | `todo` |
| `veyon.yaml` | Veyon: teachers as masters, students as agents | |
| `domain_join.yaml`, `gcpw.yaml`, `autologon.yaml`, `seb_classroom.yaml` | domain join, Google login, autologon, Safe Exam Browser | |

`win_wm.yaml` reaches every action of the collection: prefer the playbook of
one step when there is one (`software.yaml` to install, `wu_run.yaml` to
update), and `win_wm.yaml` for what no playbook does. Its `todo` takes task
strings joined by commas: `chrome,vscode`, `firefox-off`, `wol,openssh-harden`.

## Before launching

- **The PCs may be off.** A PC that does not answer is *unreachable*, not
  broken: start with `wol.yaml`, or put `wol` first in a `todo`. A PC with no
  `ansible_mac` in the inventory (a laptop on Wi-Fi) cannot be woken.
- **Read first, change after.** `sysinfo.yaml`, `wu_scan.yaml` and the
  `-info` task strings change nothing: use them to find out the state before
  proposing a change, and to compare after it.
- **Narrow the hosts** to those that need it (the limit of the launch): a
  group (`students`, `teachers`) or some PCs, not a whole lab by default.
- **Users see it.** `maint_lock`, `maint_restart`, `shutdown`, `wu_run` and
  `wu_optional` log users off or restart PCs: not during lessons unless the
  person says so. A lock is always paired with an unlock.
- **Long runs.** Windows Update and DISM repair take tens of minutes and
  restart the PCs: launch, then follow the run (its result tells host by
  host), rather than waiting in one call.

## Workflows

The steps pass on to each other which hosts are left (`wf_hosts`), which
never answered (`wf_unreachable`), which failed and why (`wf_failed`), and
which are still locked (`wf_locked`). With `wf_tolerant: true` in their
templates, a step succeeds even when some PCs fail, so one broken PC does not
stop the others, and `wf_report.yaml` at the end fails if any did, naming
them. Typical chains (links "on success" unless marked):

- **Monthly maintenance**: `wol` → `maint_lock` → `maint_restart` (pending)
  → `maint_chkdsk` → `maint_wim_scan` → `maint_sfc` → `maint_optimize`;
  then, *always*, `maint_unlock` → `maint_restart` (always) → `wf_report`.
- **Security updates**: `wol` → `sysinfo` (os) → `wu_scan` → `maint_lock` →
  `wu_run` (security); then, *always*, `maint_unlock` → `wu_pause` (1-m) →
  `sysinfo` (os) → `wf_report`.
- **Next Windows release**: `wol` → `sysinfo` → `maint_lock` →
  `wu_optional` (upgrades) → `wu_run` (security); then, *always*,
  `maint_unlock` → `sysinfo` (os) → `wf_report`.

When such a workflow exists, launch it rather than its steps one by one.

## After a run

- Say how it went host by host: done, failed (with the reason), unreachable.
  A PC that was off is not a failure of the work.
- Hosts left locked (`wf_locked` in `wf_report`) need `maint_unlock.yaml`.
- Write what was done in a report, as the skill win-edulab-reports says.
