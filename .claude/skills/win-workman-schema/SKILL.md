---
name: win-workman-schema
description: Use when writing, updating, or debugging a win_workman_<schema>_schema variable — covers all package fields, file entries, shortcuts, services, portable provider, arch-aware variants, and before/after hooks
---

# win_workman Schema Definition Reference

## What is a schema?

Every software role defines a `win_workman_<schema>_schema` dict in `vars/main.yaml`. This dict is passed as `win_workman_schema` to `pkg_utils` tasks, which use it to drive the entire install/uninstall/detect lifecycle. **No install logic lives in schema roles** — only the data definition.

---

## Full schema structure

```yaml
win_workman_<schema>_schema:
  name: <Display Name>        # human-readable, used in task labels

  package:
    # --- Detection ---
    searchName: "<Registry DisplayName>"   # matched against HKLM Uninstall DisplayName; supports glob (e.g. "App*")
    version: "<x.y.z>"                     # target version; omit for "latest"
    provider: registry                     # registry (default) | portable
    product_id: "<RegistryKeyName>"        # optional: registry key ID used for uninstall (when searchName alone is ambiguous)

    # --- Installation ---
    setup_file: installer.exe              # filename under win_workman_remote_tmp
    setup_dir: subdir                      # optional subdirectory under remote_tmp
    install_args:
      - /VERYSILENT
      - /TASKS=desktopicon

    # --- Uninstallation ---
    uninstall_args:
      - /VERYSILENT
    uninstall_before_upgrade: false        # default false; set true for MSI upgrades
    uninstall_via_helper: false            # default false; run uninstall string via PowerShell Start-Process instead of win_package (use when win_package cannot handle the uninstaller)
    uninstall_valid_rc:                    # optional; list of exit codes accepted as success by uninstall_via_helper (default [0])
      - 0
      - 19

    # --- Hooks (optional) ---
    before_install_ps_script: |
      # PowerShell run before install; $Ansible.Changed = $false to suppress change
    after_install_ps_script: |
      # PowerShell run after install
    before_uninstall_ps_script: |
      # PowerShell run before uninstall
    after_uninstall_ps_script: |
      # PowerShell run after uninstall completes

    # --- Cleanup (optional) ---
    cleanup_paths:
      - "%ProgramFiles%\\VendorDir"        # paths removed after uninstall

    # --- PATH (optional) ---
    path_dirs:
      - "%ProgramFiles%\\App\\bin"         # dirs added to Windows system PATH

    # --- Portable provider ---
    portable_dir: AppFolder               # folder under win_workman_portable_path
    # or for multiple dirs:
    portable_dirs:
      - AppFolder
      - AppData

  # --- Files to download/copy ---
  files:
    - filename: installer.exe
      url: https://...
      checksum: sha256:<hex>
      # Optional for portable:
      extract: 7z                          # extract with 7-Zip
      dest_dir: AppFolder                  # destination under win_workman_portable_path

  # --- Shortcuts (optional) ---
  shortcuts:
    - description: "<App Name>"
      src: "%ProgramFiles%\\App\\app.exe"
      dest: '%Public%\Desktop\App Name.lnk'
      icon: "%ProgramFiles%\\App\\app.exe,0"
      directory: "%ProgramFiles%\\App\\"
      arguments: "--flag value"            # optional CLI args

  # --- Windows Services (optional) ---
  services:
    - name: ServiceName
      start_mode: auto                     # auto | manual | disabled
      state: started                       # started | stopped
```

---

## Package providers

### `registry` (default)

Standard installer (NSIS, Inno Setup, MSI). Detected via `searchName` (glob pattern) against `DisplayName` in `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*`. Version compared against `package.version`.

**Required fields:** `setup_file`, `searchName`
**Optional:** `version`, `install_args`, `uninstall_args`, `product_id`

`product_id` — when set, used as the registry key name for uninstall (passed to `win_package` as `product_id`). Required when `searchName` matches multiple entries or the key name differs from the DisplayName.

```yaml
package:
  setup_file: App-1.2.3-x64.exe
  searchName: "Vendor App"
  version: "1.2.3"
  provider: registry
  install_args: [/VERYSILENT, /NORESTART]
  uninstall_args: [/VERYSILENT]
```

### `portable`

Files extracted/copied to `win_workman_portable_path` (default `C:\PortableApps`). Detected by directory/file presence, not registry. No uninstall registry entry.

**Required fields:** `portable_dir` (or `portable_dirs`)
**File entry:** usually `extract: 7z`

```yaml
package:
  provider: portable
  portable_dir: MyApp
files:
  - filename: myapp.7z
    url: https://...
    checksum: sha256:<hex>
    extract: 7z
    dest_dir: MyApp
```

---

## Shortcut fields

| Field | Required | Notes |
|-------|----------|-------|
| `description` | yes | Used in task label |
| `src` | yes | Target executable; supports `%EnvVar%` |
| `dest` | yes | `.lnk` path; supports `%EnvVar%` |
| `icon` | no | `path,index` format |
| `directory` | no | Working directory for the shortcut |
| `arguments` | no | CLI arguments passed to the executable |

`%Public%\Desktop\` → all-users desktop  
`%ProgramData%\Microsoft\Windows\Start Menu\Programs\` → all-users Start Menu

---

## Architecture-aware schema

When a role supports 32/64-bit via task arguments (`chrome-on-32bit`), use a computed variable to select the right fields:

```yaml
# Read arch from task argv (set by dispatcher)
win_workman_<schema>_arch: >-
  {{
    "32bit" if ("32bit" in (win_workman_task_argv | default([])))
    else "64bit"
  }}

win_workman_<schema>_filename:
  64bit: app-x64.msi
  32bit: app-x86.msi

win_workman_<schema>_checksum:
  64bit: sha256:<hex64>
  32bit: sha256:<hex32>

win_workman_<schema>_schema:
  name: My App
  package:
    setup_file: "{{ win_workman_<schema>_filename[win_workman_<schema>_arch] }}"
    searchName: "My App"
    version: "1.0"
    provider: registry
    install_args: [/quiet]
    uninstall_args: [/quiet]
  files:
    - filename: "{{ win_workman_<schema>_filename[win_workman_<schema>_arch] }}"
      url: "{{ win_workman_<schema>_url[win_workman_<schema>_arch] }}"
      checksum: "{{ win_workman_<schema>_checksum[win_workman_<schema>_arch] }}"
```

---

## Before/After hook pattern

Use `before_uninstall_ps_script` to kill running processes before uninstall:

```yaml
win_workman_<schema>_kill_script: |
  $Ansible.Changed = $false
  $process = Get-Process -Name myapp -ErrorAction SilentlyContinue
  if ($process) {
      Stop-Process -InputObject $process -Force:$true
      $Ansible.Changed = $true
  }

win_workman_<schema>_schema:
  name: My App
  package:
    before_uninstall_ps_script: "{{ win_workman_<schema>_kill_script }}"
    ...
```

---

## Computed shortcuts

Shortcuts can include Jinja2 expressions evaluated at role load time:

```yaml
win_workman_<schema>_schema:
  ...
  shortcuts: >-
    {{
      win_workman_<schema>_shortcuts_list
      if win_workman_<schema>_show_shortcut | bool
      else []
    }}
```

---

## Common mistakes

| Mistake | Fix |
|---------|-----|
| `searchName` doesn't match registry | Run `Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' \| Select DisplayName` on target; `searchName` supports glob (e.g. `"App*"`) |
| Uninstall fails with win_package | Set `uninstall_via_helper: true` to run uninstall via PowerShell `Start-Process`; also check `product_id` matches the registry key name |
| Uninstall succeeds but returns non-zero rc | Set `uninstall_via_helper: true` and add `uninstall_valid_rc: [0, <rc>]` to accept the specific exit code as success (e.g. Vivaldi returns 19) |
| Checksum mismatch | Run `sha256sum <file>` on the installer you stored; re-download if needed |
| Portable role not detected | Ensure `portable_dir` matches the actual folder name under `C:\PortableApps` |
| Version comparison fails | Ensure `package.version` uses the same format as `DisplayVersion` in registry (e.g., `1.2.3` not `1.2`) |
| Shortcut not created | Check `%EnvVar%` expansion — use `%Public%` not `$env:Public` |
