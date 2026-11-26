---
name: win-edulab-reports
description: Writing the report of an intervention on a lab - maintenance,
  Windows Update, a repair, an incident, an audit, a change of configuration or
  software - and keeping the state of each lab, in Fleet's documents. Read it
  before writing or updating a report or the status of a lab.
---

# Reports of interventions

The documents of Fleet keep, for every lab, what was done on it and its
state. Search them before writing (`doc_search`): add to what is there
rather than starting another.

## Where

```
labs/<inventory>/README.md                  index of the lab, newest first
labs/<inventory>/status.md                  the state of the lab now
labs/<inventory>/<YYYY-MM-DD>-<type>.md     one report per intervention
dossiers/<subject>.md                       a problem followed over time
```

`<inventory>` is the name of the lab's inventory in Fleet. The date is the
day of the intervention. Two of the same type on one day: a suffix `-2`.

| Type | Intervention |
|---|---|
| `maintenance` | the maintenance (lock, disk and system checks, unlock) |
| `wu` | Windows Update |
| `wim-repair` | repair of the component store |
| `incident` | a fault or anomaly handled out of plan |
| `audit` | a survey of the state, nothing changed on the hosts |
| `config` | a change of configuration of hosts (network, name, domain, policy) |
| `software` | software installed, updated or removed |

## A report

A report records one intervention and is not changed afterwards:

1. **Heading**: lab, date and time, what was run (templates, workflow), how
   many hosts, the outcome in one line.
2. **Outcome by step**, in a table: step, hosts done, failed, unreachable.
3. **Anomalies**, host by host: only those, each with what was seen and
   what was done or is left to do.
4. **To do**: what is left, and for whom.
5. **Runs**: the runs of Fleet it is based on, as links (`fleet:run/<id>`).

Then add a line at the top of the lab's `README.md`, and bring `status.md`
up to date (what is installed, the Windows release, the hosts with open
problems). Take what the report says from the runs, never from memory: a
PC that was off is "unreachable", not "failed".

## A dossier

A problem followed over time (a fault that comes back, a procedure worked
out across interventions) goes in a dossier, updated as it goes: cause,
procedure, open questions. Reports link to it.

## Never in a document

Passwords, keys, tokens, licence keys: documents are read by everyone who
uses Fleet.
