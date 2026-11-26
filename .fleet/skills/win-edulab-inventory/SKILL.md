---
name: win-edulab-inventory
description: How an inventory of a lab of ansible-win_edulab is laid out -
  the groups teachers, students and win_managed, the variables each PC needs
  (address, MAC address for Wake-on-LAN), and where the lab's own settings go.
  Read it before reading, adding or changing hosts or variables of a lab.
---

# The inventory of a lab

One inventory per lab (or per set of classroom PCs), each a tree:

```
hosts.yaml                       hosts and groups
group_vars/all/vars.yaml         settings of the whole lab: account, keys, storage, URLs
group_vars/teachers/vars.yaml    the teacher's PC (Veyon master, ...)
group_vars/students/vars.yaml    the students' PCs
group_vars/win_managed/vars.yaml how Ansible connects to the Windows PCs (SSH, PowerShell)
host_vars/<HOST>.yaml            what one PC does differently
```

## Groups

- **Role groups** say what a PC is: `teachers` and `students`. Each PC is
  declared once, in its role group, with its address and MAC address.
- **`win_managed`** is every Windows PC Ansible manages, built from the role
  groups (`children`), never by repeating hosts. The playbooks run on it by
  default, and it carries the connection settings.
- A set of classroom PCs has no teacher/student split: one flat group, and
  `win_managed` lists the PCs ready for Ansible.
- Other groups may say something the playbooks read: a licence, a set of
  software (`win_edulab_software` in a group's vars), a spare PC.

```yaml
all:
  children:
    teachers:
      hosts:
        DOC:
          ansible_host: 10.0.1.100
          ansible_mac: 00:11:22:33:44:55
    students:
      hosts:
        PC01:
          ansible_host: 10.0.1.101
          ansible_mac: 00:11:22:33:44:56
    win_managed:
      children:
        teachers:
        students:
```

## What a PC needs

- `ansible_host`: its address. Fixed: the labs work by address.
- `ansible_mac`: the MAC address of its wired card, for `wol.yaml`. Without
  it the PC cannot be woken, and is maintained only when found on.
- Its account and keys come from `group_vars/all`, its passwords from the
  credentials and secret variables of Fleet, never written in the files.

## Changing an inventory

- Adding a PC: one entry in its role group, with address and MAC address;
  `win_managed` picks it up by itself.
- A setting of the whole lab goes in `group_vars/all/vars.yaml`; one of a
  role in its group's file; one of a PC in `host_vars`. A child group wins
  over its parents (`students` over `win_managed`), and Ansible does not merge
  lists: a host in two groups that both set a list gets one of them.
- Variables are named after the role that reads them, `win_workman_<role>_*`
  (see the catalog of the skill win-workman).
- No passwords, keys or tokens in these files.
