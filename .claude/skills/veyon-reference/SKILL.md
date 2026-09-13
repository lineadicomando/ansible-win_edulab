---
name: veyon-reference
description: Use when designing Veyon access control rules (deny-by-default, conditions, AND/OR/NOT, rule order) or wiring Veyon to LDAP/Active Directory including Samba AD DC (bind DN, object trees, attribute mapping, filters, computer locations) — the parts the win_workman veyon role does not manage. Trigger: veyon access control, AccessControl/Rules, veyon LDAP, veyon ldap query, base DN, deny-by-default
---

# Veyon — access control and LDAP reference

Scope note: the `win_workman` veyon role manages installation, the authentication
keypair, the auth method and lab network objects. It does **not** write access control
rules or LDAP settings. Those are set in the Veyon Configurator, or pushed with
`veyon-cli config set` / `config import` from a `local/` playbook. For the role itself see
**veyon-deploy**.

---

## Access control rules

**Access is denied by default.** An empty rule list denies everything, so at least one
explicit *Allow* rule is required. Rules are evaluated in order and **the first match
wins**.

### Rule anatomy

*General*: name (required), description, *always process* (apply the action without
evaluating conditions), *invert conditions* (logical NOT over all of them).

*Conditions* — multiple conditions in one rule are **AND**ed:

| Condition | True when |
|-----------|-----------|
| Member of user group | The connecting user is in the named group |
| Computer location | The client computer is in the named location |
| Same location | Accessing and client computer share a location |
| Access to localhost | The Master is connecting to its own computer |
| Common groups | Master user and client user share at least one group |
| User already logged on | Someone is logged in on the client |
| No user logged on | The client sits at the login screen |

*Action*: allow access, deny access, ask the logged-on user, or none (rule disabled).

**OR** is expressed as separate rules; **NOT** as *invert conditions*.

### Ordering

Specific rules on top, general ones at the bottom, with a final catch-all. The usual
school shape:

```
[1] Localhost access          → condition: access to localhost           → allow
[2] Teachers                  → condition: member of group "Teachers"    → allow
[3] Deny everything else      → always process, no conditions            → deny
```

Restricting a teacher to their own classroom is rule 2 plus a second condition, *same
location*. Dropping rule 3 means everyone gets in; putting it first means nobody does.

### In the config file

Rules live in the Veyon JSON config under `AccessControl/Rules`:

```json
{
  "AccessControl/Rules": [
    { "Name": "Localhost", "Action": 1, "Conditions": { "IsLocalhost": true } },
    { "Name": "Teachers",  "Action": 1, "Conditions": { "UserInGroup": "Teachers" } },
    { "Name": "Deny all",  "Action": 2, "AlwaysProcess": true }
  ]
}
```

Rules must be present on **every client** that has to honour them — they are enforced by
the Service, not by the Master. Deploy with `veyon-cli config import <file>` and restart
`VeyonService`.

### Testing

Configurator → Access control → **Test**: enter the connecting username, the accessing
hostname and the client hostname; it reports which rule matched and the outcome. Group
conditions can be cross-checked with `veyon-cli ldap query groups`.

| Symptom | Cause | Fix |
|---------|-------|-----|
| Denied despite a correct allow rule | A deny rule matches first | Move the allow rule above it |
| Everyone gets access | No final deny rule | Append a deny rule with no conditions |
| Group condition never matches | Group not resolvable via LDAP | `veyon-cli ldap query groups` |
| Rules ignored on clients | Config never imported there | Re-import on every client |

---

## LDAP / Active Directory

LDAP lets Veyon populate locations and computers from the directory and resolve group
membership for the rules above. OpenLDAP and Active Directory are both supported, Samba
AD DC included — which is what this project runs.

### Basic settings

| Field | OpenLDAP | AD / Samba |
|-------|----------|------------|
| Server | `ldap.example.test` | `dc01.example.test` |
| Port | 389, or 636 for LDAPS | 389 / 636 |
| Bind DN | `cn=veyon,ou=serviceaccounts,dc=example,dc=test` | `CN=veyon,CN=Users,DC=example,DC=test` |

Use a dedicated service account and authenticated bind; anonymous bind only if the server
allows it and the data is not sensitive. The bind password belongs in the vault — see
**win-edulab-vault**.

Discover the base DN rather than guessing it:

```bash
veyon-cli ldap autoconfigurebasedn ldap://192.168.1.2/
veyon-cli ldap autoconfigurebasedn ldap://dc01/ cn=veyon,dc=example,dc=test <password>
```

### Object trees and attributes

Trees are given **relative to the base DN**. Enable recursive search when objects sit in
sub-OUs.

| | OpenLDAP | AD / Samba |
|---|---|---|
| Users tree | `ou=users` | `CN=Users` or a dedicated OU |
| Groups tree | `ou=groups` | `CN=Users` or a dedicated OU |
| Computers tree | `ou=computers` | `CN=Computers` or a dedicated OU |
| User login attribute | `uid` | `sAMAccountName` |
| Group member attribute | `memberUid` or `member` | `member` (full DN) |
| Hostname attribute | `cn` | `cn` or `dNSHostName` |

Filters use RFC 2254 syntax:

```ldap
(objectClass=computer)
(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))   # enabled users, AD
(&(objectClass=group)(cn=veyon-*))
```

### Samba AD DC specifics

- `sAMAccountName` for the login attribute, `member` for group membership
- member identification: *distinguished names (AD/Samba)*
- nested groups work with *query all indirect group memberships* enabled
- LDAPS against Samba may need `ldap server require strong auth = no` on the DC

### Computer locations

Pick how Veyon groups computers: by **computer groups** (one group per classroom), by
**containers/OUs** (when the OU tree mirrors the classrooms), or by a **custom attribute**
on the computer object. Then set Configurator → Locations and computers → Backend →
**LDAP**, which replaces the manual backend.

Note that this project's `win_workman_veyon_labs` populates locations from the **Ansible
inventory** instead. Use one or the other, not both — see **veyon-deploy**.

### Verifying

```bash
veyon-cli ldap query users
veyon-cli ldap query groups
veyon-cli ldap query computers
veyon-cli ldap query locations
```

| Symptom | Cause | Fix |
|---------|-------|-----|
| Connection refused | Wrong host or port | Check firewall and 389/636 |
| Bind failed | Service account DN or password wrong | Re-check the bind DN and the vault value |
| No computers returned | Base DN or filter wrong | `veyon-cli ldap query computers` and widen the filter |
| Groups empty | Wrong member attribute | Switch between `memberUid` and `member` |
| Locations empty | Backend still manual | Set the backend to LDAP |
| User not seen in a group | Nested groups | Enable indirect group membership queries |

---

## Classroom features, for reference

Driven from the Master GUI or `veyon-cli`: `demo start|stop` (port 11400),
`lock start|stop`, `remoteaccess <host>`, `power on|reboot|shutdown <host>`,
`message send "<text>"`, `filetransfer send <src> <dest>`, `screenshot <host> <path>`,
`config get|set|import|export`, `networkobjects`, `authkeys`, `service status|start|stop`.

Wake-on-LAN needs the MAC in the network objects and WoL enabled in firmware. This
project wakes machines with the `wol` role instead, off `ansible_mac` from the inventory.
