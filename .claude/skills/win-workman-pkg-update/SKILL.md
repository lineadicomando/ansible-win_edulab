---
name: win-workman-pkg-update
description: Use when bumping a win_workman package role to a newer upstream version — covers version discovery per vendor, obtaining the sha256 without downloading where possible, the fields to edit in vars/main.yaml, the catalog doc that also carries the version, the separate git repo the collection lives in, and the commit convention
---

# Bumping a win_workman Package Role

## Overview

A version bump touches four things: the installer filename, the `version` field, the
download URL and the sha256 checksum — plus the catalog doc, which repeats the installer
name. Everything else in the schema (`install_args`, `uninstall_args`,
`uninstall_valid_rc`, hooks) stays put unless the test says otherwise.

For what each schema field *means*, see `win-workman-schema`. For validating the bump on
a VM, see `win-workman-pkg-test`. This skill covers only the bump procedure.

---

## Before anything: the collection is a separate git repo

`ansible_collections/lineadicomando/win_workman` is a **symlink** to a checkout of
`github.com/lineadicomando/ansible-collection-win_workman` (same for `samba_ad_dc`).
Editing a role leaves `git status` in `ansible-win_edulab` completely clean, and
`git check-ignore` on the path fails with *"is beyond a symbolic link"* — the message is
localised, so match on the failure, not the wording.

Run every git command inside the collection:

```bash
cd ansible_collections/lineadicomando/win_workman
git status --short
```

---

## Procedure

### 1. Read the current state

```bash
grep -nE 'setup_file|version:|filename|url:|checksum' \
  ansible_collections/lineadicomando/win_workman/roles/<role>/vars/main.yaml
```

Note whether the URL is literal or templated. Roles like `firefox`, `opera`,
`libreoffice` and `laragon` build the URL from a version variable — there the bump is one
variable, not four strings.

### 2. Find the latest upstream version

Sources differ by vendor; see the table below. When scraping an HTML download page, the
page often lists old releases too — sort the matches and check the result is plausible
rather than taking the first hit. Cross-check the answer against `last-modified` on the
installer:

```bash
curl -sIL --max-time 30 "<url>" | grep -iE '^(HTTP|content-length|last-modified)'
```

### 3. Get the sha256 — preferably without downloading

**GitHub releases (17 roles): use the API, never download.** Each asset carries a
`digest` field that is exactly the value the schema needs:

```bash
curl -s "https://api.github.com/repos/<owner>/<repo>/releases/tags/<tag>" |
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(a['name'], a.get('digest')) for a in d['assets']]"
```

Verified to match the recorded checksum byte for byte (`notepadpp` 8.9.5). This saves a
multi-hundred-MB download per bump.

**Other vendors:** try the sidecar/digest file first (table below). Only when no digest
is published, download and hash:

```bash
cd /tmp && curl -s --max-time 300 -o pkg.exe "<url>" && sha256sum pkg.exe && rm -f pkg.exe
```

Do not guess a sidecar exists — probe it, it costs one request:

```bash
for s in .sha256 .sha256sum .asc; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' -IL --max-time 15 "<url>$s")  $s"
done
```

### 4. Edit `vars/main.yaml`

Fields to change, all of them:

| Field | Under | Note |
|---|---|---|
| `setup_file` | `package` | installer filename |
| `version` | `package` | used for the upgrade comparison |
| `filename` | `files[]` | must equal `setup_file` |
| `url` | `files[]` | must end with `filename` |
| `checksum` | `files[]` | `sha256:<hex>`, lowercase, no prefix space |

A one-shot `sed` over the old version string catches filename, url and `setup_file`
together; `version:` and `checksum:` need their own expressions.

Arch-aware roles (`seb`, `edge`, `p7zip`, `gcpw`, `chrome`, `firefox`) keep `url` and
`checksum` as per-arch dicts that `files[]` references through
`win_workman_<role>_arch`. There the edit lands in the dicts, and **every** architecture
needs its own hash — bumping only `64bit` leaves 32-bit hosts failing on checksum.

Leave `searchName`, `install_args`, `uninstall_args`, `uninstall_valid_rc`,
`cleanup_paths` and the hook scripts untouched. If the test later fails, *then* revisit
them — a new major is the usual reason.

### 5. Update the catalog doc

`docs/roles/catalog/<role>.md` carries an `Installer:` line that repeats the filename:

```
Installer: `Vivaldi.8.2.4133.52.x64.exe`
```

45 of the catalog docs have this line. Some use a wildcard (`gimp-*.exe`) or a
placeholder (`Opera_<version>_Setup_x64.exe`) and need no edit; the ones with a literal
version do. Check before committing:

```bash
cd ansible_collections/lineadicomando/win_workman
grep -oE 'Installer: `[^`]+`' docs/roles/catalog/<role>.md
```

### 6. Test on a VM

A bump is not done until the pkg lifecycle passes from a clean snapshot. Follow
`win-workman-pkg-test`: revert to `baseline`, `wol`, `secure_ssh`, then
`info → download → copy → on → on → info → is_present → off → is_present → info`.

`download` succeeding *is* the checksum check — `get_url` fails on a mismatch, so a green
download proves the hash.

Pay attention on a major version jump: `install_args` and the uninstall path are the
parts that break. After `off`, confirm the install directory and shortcuts are really
gone — **on the filesystem**, not from `info`, which reads the registry and reports a
package absent as soon as its uninstall entry is deleted. A green `off` followed by a
green `info` is not proof: `dbeaver` passed both while leaving 177 MB behind, because the
NSIS uninstaller had been reported done while it was still running. If the bump is the
first real test the role has had, budget for finding that kind of defect — see
`win-workman-pkg-test`.

### 7. Commit and push

English, imperative, one line naming the product and the new version:

```
Update Vivaldi to 8.2.4133.52
```

The body says where the checksum came from and that the lifecycle test passed. Bumps are
the most frequent commit type in the collection — match the existing log.

```bash
cd ansible_collections/lineadicomando/win_workman
git add roles/<role>/vars/main.yaml docs/roles/catalog/<role>.md
git commit && git push origin main
```

---

## Version and checksum sources by vendor

Probed values, not assumptions. `sidecar` = a digest file next to the installer.

| Vendor / roles | Version source | sha256 without downloading |
|---|---|---|
| GitHub releases — `dbeaver`, `embarcadero_devcpp`, `git`, `laragon`, `netbeans`, `notepadpp`, `ntop`, `peazip`, `powertoys`, `rustdesk`, `seb`, `tinycad`, `veyon`, `windirstat`, `winfsp`, `winmerge` | `/releases/latest` or the API `tags` endpoint | **yes** — asset `digest` field in the API |
| Visual Studio Code — `vscode` | `update.code.visualstudio.com/api/update/win32-x64/stable/latest` | **yes** — the same JSON carries `productVersion`, `url` and `sha256hash` |
| Mozilla — `firefox` | `download-installer.cdn.mozilla.net/pub/firefox/releases/` | **yes** — `<version>/SHA256SUMS` (HTTP 200 confirmed) |
| Python — `python31x` | `python.org/ftp/python/` directory listing | no sidecar (`.sha256` → 404); the release page publishes an md5, so download and hash |
| Vivaldi | `vivaldi.com/download/` (page lists old versions too — filter) | no (`.sha256` and `.sha256sum` → 404) |
| Blender | `download.blender.org/release/` | no (`.sha256` → 404) |
| LibreOffice | mirror directory listing | no (`.sha256sum` → 404) |
| Evergreen "latest" URLs — `chrome`, `edge`, `gcpw`, `googledrive`, `vcredist14`, `brave`, `postman` | URL carries no version; read the shipped version from the vendor's release notes, or install and check `info` | n/a — the file behind the stable URL changes silently. `chrome` omits `checksum` for this reason; `edge` keeps one and needs a re-hash at every bump |
| Autodesk — `autocadlt2026` | download portal, per-locale URLs | no — these are multi-part archives, hash each part |

For an MSI where the bump also needs a new `ProductCode`, extract it with
`python3` + `olefile` (no msitools on this machine).

---

## Traps

- **`git status` clean after editing a role** — you are in the wrong repo. See the top of
  this file.
- **Scraped version looks wrong** — download pages list archived releases; sorting the
  matches surfaced `5.6.2867.62` alongside `8.2.4133.52` for Vivaldi.
- **Stale catalog doc** — easy to forget step 5. `adobe_reader_dc` is still drifted
  this way in the repo; `vscode` was, and was realigned when it was bumped to 1.137.0.
- **`download` re-downloads every run afterwards** — the checksum does not match the
  file; re-hash rather than deleting the field.
- **Templated URL roles** — editing the literal string does nothing when the URL is built
  from `win_workman_<role>_version`. Read the whole file before `sed`.
