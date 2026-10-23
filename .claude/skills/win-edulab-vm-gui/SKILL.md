---
name: win-edulab-vm-gui
description: Use when a test needs to see or act on the desktop of a test VM as a user would — screenshots, clicks, typing, graphical logon — through tools/vm/vmgui.py from the hypervisor, with nothing installed in the guest. Also for diagnosing a VM that SSH cannot reach (stalled install, logon screen, error dialogs)
---

# Driving a test VM's screen from the hypervisor

`tools/vm/vmgui.py` takes screenshots with `virsh screenshot`, sends keys with
`virsh send-key` and moves the mouse with the QMP command `input-send-event`. It works
whatever state the guest is in: firmware, Windows Setup, logon screen, desktop. VM lifecycle
and resources: skill `win-edulab-test-vms`. Permissions for typing passwords:
`CLAUDE.local.md`.

## When to use it — and when not

Use it for what only the screen shows: the logon screen and its user list, a wallpaper or
lock screen policy, a dialog an installer leaves open, Veyon or SEB windows, an
installation that stalled before SSH was up. Use it to act as a student or teacher would.

Do not use it where Ansible or `run_powershell` can answer: every screenshot costs tokens,
coordinates break when a window moves, and waits are guesses. Regression tests stay in
Ansible; the GUI confirms what Ansible cannot see.

## Commands

```bash
tools/vm/vmgui.py teacher shot login          # /tmp/vmgui/<domain>/login.png 1280x800
tools/vm/vmgui.py teacher click 640 400       # pixels of the last screenshot
tools/vm/vmgui.py teacher click 640 400 --right
tools/vm/vmgui.py teacher click 640 400 --double
tools/vm/vmgui.py teacher scroll 3            # wheel down; -3 up
tools/vm/vmgui.py teacher key KEY_LEFTMETA KEY_R
tools/vm/vmgui.py teacher type 'notepad' --enter
tools/vm/vmgui.py teacher vault ansible_vault_password --enter
```

- `<vm>`: inventory host or libvirt domain. `--inventory` selects another inventory:
  a name under `inventories/` or the path of another project's inventory.
- `secret FILE KEY` types a value from a `KEY=VALUE` file (a project's `.env`), for
  inventories without a vault. Same rule: only `KEY typed` is printed.
- `type` uses the guest layout, Italian by default (`--layout us` otherwise); it refuses
  characters missing from the layout instead of typing something else.
- `vault VAR` types a top-level variable of `inventories/<inv>/group_vars/all/vault.yaml`
  and prints only `VAR typed`. Never print, log or echo the value some other way.
- Key names are Linux input names: `KEY_ENTER`, `KEY_ESC`, `KEY_TAB`, `KEY_LEFTMETA`
  (Windows key), `KEY_LEFTCTRL KEY_LEFTALT KEY_DELETE`, `KEY_F5`.

## Working loop

1. `shot`, then read the PNG with the Read tool. Never click blind.
2. Act: one click or one key chord.
3. Wait for the guest (1-3 s for UI, longer for an app start), `shot` again, check the
   effect before the next action.

Keep screenshots few and named after the step; they stay in `/tmp/vmgui/`.

## Practical notes (Windows 11)

- Logon: the first key only lifts the lock screen. Send `KEY_ENTER`, wait 3 s, then
  `vault ... --enter`; typed too early, the password is wrong.
- Logging on as another user: on the logon screen pick "Altro utente" (Other user) or
  the account tile, then type `SCHOOL\student-alice` with `type`, then the password with
  `vault`.
- Browser address bar: `key KEY_LEFTCTRL KEY_L`, `type <url>`, then `key KEY_DELETE`
  before `KEY_ENTER`, or Edge completes the address from history.
- Coordinates move if a window is not maximised: maximise first (`KEY_LEFTMETA KEY_UP`).
- A black screenshot usually means the display is off: send `KEY_LEFTSHIFT` or move the mouse.
