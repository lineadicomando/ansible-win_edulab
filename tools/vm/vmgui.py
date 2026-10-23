#!/usr/bin/env python3
"""Drive the screen, keyboard and mouse of a test VM from the hypervisor.

Nothing is installed in the guest: screenshots come from `virsh screenshot`, keys
from `virsh send-key`, the mouse from the QMP command `input-send-event` (the VM
needs a USB tablet, which tests/vm_build_windows.yaml adds).

    vmgui.py <vm> shot [name]            save a PNG, print its path and size
    vmgui.py <vm> click X Y [--right] [--double]
    vmgui.py <vm> move X Y
    vmgui.py <vm> scroll N               wheel: N > 0 down, N < 0 up
    vmgui.py <vm> key KEY_LEFTCTRL KEY_L press a chord (Linux input key names)
    vmgui.py <vm> type "text" [--enter]  type text with the guest keyboard layout
    vmgui.py <vm> vault VAR [--enter]    type a vault variable, never printing it

<vm> is an inventory host (teacher) or a libvirt domain (win_edulab-teacher).
X and Y are pixels of the last screenshot: take one before clicking.
Options: --inventory NAME (default school), --layout it|us (default it).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URI = os.environ.get('LIBVIRT_DEFAULT_URI', 'qemu:///system')
SHOTS = Path(os.environ.get('VMGUI_DIR', '/tmp/vmgui'))


def virsh(*args, capture=False):
    return subprocess.run(['virsh', '-c', URI, *args], check=True, text=True,
                          stdout=subprocess.PIPE if capture else subprocess.DEVNULL).stdout


def resolve(vm, inventory):
    """Inventory host -> libvirt domain; a domain name is returned as it is."""
    names = virsh('list', '--all', '--name', capture=True).split()
    if vm in names:
        return vm
    out = subprocess.run(['ansible-inventory', '-i', f'inventories/{inventory}', '--host', vm],
                         cwd=ROOT, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        sys.exit(f'{vm}: neither a libvirt domain nor a host of inventory {inventory}')
    domain = json.loads(out.stdout).get('libvirt_domain')
    if not domain:
        sys.exit(f'{vm}: no libvirt_domain in inventory {inventory}')
    return domain


# Keyboard layouts: character -> chord of Linux input key names.
def layout_it():
    s, g = 'KEY_LEFTSHIFT', 'KEY_RIGHTALT'
    m = {}
    for c in 'abcdefghijklmnopqrstuvwxyz':
        m[c] = ['KEY_' + c.upper()]
        m[c.upper()] = [s, 'KEY_' + c.upper()]
    for c in '1234567890':
        m[c] = ['KEY_' + c]
    for c, k in zip('!"£$%&/()=', '1234567890'):
        m[c] = [s, 'KEY_' + k]
    m.update({
        "'": ['KEY_MINUS'], '?': [s, 'KEY_MINUS'], 'ì': ['KEY_EQUAL'], '^': [s, 'KEY_EQUAL'],
        'è': ['KEY_LEFTBRACE'], 'é': [s, 'KEY_LEFTBRACE'], '[': [g, 'KEY_LEFTBRACE'],
        '{': [g, s, 'KEY_LEFTBRACE'], '+': ['KEY_RIGHTBRACE'], '*': [s, 'KEY_RIGHTBRACE'],
        ']': [g, 'KEY_RIGHTBRACE'], '}': [g, s, 'KEY_RIGHTBRACE'], 'ò': ['KEY_SEMICOLON'],
        'ç': [s, 'KEY_SEMICOLON'], '@': [g, 'KEY_SEMICOLON'], 'à': ['KEY_APOSTROPHE'],
        '°': [s, 'KEY_APOSTROPHE'], '#': [g, 'KEY_APOSTROPHE'], 'ù': ['KEY_BACKSLASH'],
        '§': [s, 'KEY_BACKSLASH'], '\\': ['KEY_GRAVE'], '|': [s, 'KEY_GRAVE'],
        ',': ['KEY_COMMA'], ';': [s, 'KEY_COMMA'], '.': ['KEY_DOT'], ':': [s, 'KEY_DOT'],
        '-': ['KEY_SLASH'], '_': [s, 'KEY_SLASH'], '<': ['KEY_102ND'], '>': [s, 'KEY_102ND'],
        ' ': ['KEY_SPACE'], '\n': ['KEY_ENTER'], '\t': ['KEY_TAB'],
    })
    return m


def layout_us():
    s = 'KEY_LEFTSHIFT'
    m = {}
    for c in 'abcdefghijklmnopqrstuvwxyz':
        m[c] = ['KEY_' + c.upper()]
        m[c.upper()] = [s, 'KEY_' + c.upper()]
    for c in '1234567890':
        m[c] = ['KEY_' + c]
    for c, k in zip('!@#$%^&*()', '1234567890'):
        m[c] = [s, 'KEY_' + k]
    for plain, shifted, key in [('-', '_', 'MINUS'), ('=', '+', 'EQUAL'), ('[', '{', 'LEFTBRACE'),
                                (']', '}', 'RIGHTBRACE'), (';', ':', 'SEMICOLON'),
                                ("'", '"', 'APOSTROPHE'), ('`', '~', 'GRAVE'),
                                ('\\', '|', 'BACKSLASH'), (',', '<', 'COMMA'), ('.', '>', 'DOT'),
                                ('/', '?', 'SLASH')]:
        m[plain] = ['KEY_' + key]
        m[shifted] = [s, 'KEY_' + key]
    m.update({' ': ['KEY_SPACE'], '\n': ['KEY_ENTER'], '\t': ['KEY_TAB']})
    return m


LAYOUTS = {'it': layout_it, 'us': layout_us}


def type_text(domain, text, layout, delay):
    keys = LAYOUTS[layout]()
    missing = sorted({c for c in text if c not in keys})
    if missing:
        sys.exit(f'characters not in layout {layout}: {len(missing)}')
    for c in text:
        virsh('send-key', domain, *keys[c])
        time.sleep(delay)


def qmp(domain, events):
    virsh('qemu-monitor-command', domain,
          json.dumps({'execute': 'input-send-event', 'arguments': {'events': events}}))


def screen_size(domain):
    size = SHOTS / domain / 'size'
    if not size.exists():
        shot(domain, 'size-probe', quiet=True)
    w, h = size.read_text().split()
    return int(w), int(h)


def move(domain, x, y):
    w, h = screen_size(domain)
    qmp(domain, [{'type': 'abs', 'data': {'axis': 'x', 'value': round(x * 32767 / (w - 1))}},
                 {'type': 'abs', 'data': {'axis': 'y', 'value': round(y * 32767 / (h - 1))}}])


def button(domain, name, down):
    qmp(domain, [{'type': 'btn', 'data': {'down': down, 'button': name}}])


def shot(domain, name, quiet=False):
    folder = SHOTS / domain
    folder.mkdir(parents=True, exist_ok=True)
    raw, png = folder / f'{name}.screen', folder / f'{name}.png'
    virsh('screenshot', domain, str(raw))
    # virsh writes whatever format QEMU produces (PPM with QXL, sometimes PNG).
    # ImageMagick guesses the format from the extension, so name it by its magic.
    head = raw.read_bytes()[:8]
    if head.startswith(b'\x89PNG'):
        raw.replace(png)
    else:
        fmt = 'ppm' if head[:1] == b'P' else 'raw'
        subprocess.run(['magick', f'{fmt}:{raw}', str(png)], check=True)
        raw.unlink()
    size = subprocess.run(['magick', 'identify', '-format', '%w %h', str(png)],
                          check=True, capture_output=True, text=True).stdout.strip()
    (folder / 'size').write_text(size)
    if not quiet:
        print(png, size.replace(' ', 'x'))


def vault_value(inventory, var):
    vault = ROOT / 'inventories' / inventory / 'group_vars' / 'all' / 'vault.yaml'
    out = subprocess.run(['ansible-vault', 'view', str(vault)], cwd=ROOT, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        sys.exit(f'cannot open {vault.relative_to(ROOT)}')
    import yaml
    data = yaml.safe_load(out.stdout) or {}
    if var not in data:
        sys.exit(f'{var} is not in {vault.relative_to(ROOT)}')
    return str(data[var])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('vm')
    p.add_argument('action', choices=['shot', 'click', 'move', 'scroll', 'key', 'type', 'vault'])
    p.add_argument('args', nargs='*')
    p.add_argument('--inventory', default='school')
    p.add_argument('--layout', default='it', choices=sorted(LAYOUTS))
    p.add_argument('--enter', action='store_true')
    p.add_argument('--right', action='store_true')
    p.add_argument('--double', action='store_true')
    a = p.parse_args()
    domain = resolve(a.vm, a.inventory)

    if a.action == 'shot':
        shot(domain, a.args[0] if a.args else 'shot')
    elif a.action in ('click', 'move'):
        x, y = (int(v) for v in a.args[:2])
        move(domain, x, y)
        if a.action == 'click':
            name = 'right' if a.right else 'left'
            for _ in range(2 if a.double else 1):
                time.sleep(0.1)
                button(domain, name, True)
                time.sleep(0.08)
                button(domain, name, False)
    elif a.action == 'scroll':
        n = int(a.args[0])
        for _ in range(abs(n)):
            name = 'wheel-down' if n > 0 else 'wheel-up'
            button(domain, name, True)
            button(domain, name, False)
            time.sleep(0.05)
    elif a.action == 'key':
        virsh('send-key', domain, *a.args)
    elif a.action == 'type':
        type_text(domain, ' '.join(a.args), a.layout, 0.03)
    elif a.action == 'vault':
        # Slower than plain text: the Windows logon box drops keys typed too fast.
        type_text(domain, vault_value(a.inventory, a.args[0]), a.layout, 0.08)
        print(f'{a.args[0]} typed')
    if a.enter and a.action in ('type', 'vault'):
        virsh('send-key', domain, 'KEY_ENTER')


if __name__ == '__main__':
    main()
