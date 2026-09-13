---
name: win-workman-seb-config
description: Use when writing, auditing or looking up a win_workman_seb_client_settings block for Safe Exam Browser on Windows — covers the seb role actions, the baseline exam lockdown, every key that is effective on Windows SEB 3.x with its default, and the Mac/iOS/deprecated keys that silently do nothing. Trigger: seb, SebClientSettings, win_workman_seb_client_settings, seb-deploy, clipboardPolicy, URLFilterRules, exam lockdown
---

# Safe Exam Browser configuration — win_workman

Windows SEB 3.x (Chromium-based) only. The Mac and iOS keys in the upstream
specification are accepted by the config writer and then ignored by the client, so a
setting that "does nothing" is usually a platform mismatch rather than a syntax error.

Installed version: see `roles/seb/vars/main.yaml` in the collection.

---

## The role

| Task | Effect |
|------|--------|
| `seb` | Install SEB (pulls in `vcredist14` as a dependency) |
| `seb-off` | Uninstall |
| `seb-deploy` | Render `win_workman_seb_client_settings` and write it to the target |
| `seb-undeploy` | Remove the deployed `.seb` file |
| `seb-config_key` | Report the Config Key for the current settings |

| Variable | Default |
|----------|---------|
| `win_workman_seb_client_settings` | baseline dict in `roles/seb/defaults/main.yaml` |
| `win_workman_seb_client_settings_dest` | `C:\ProgramData\SafeExamBrowser\SebClientSettings.seb` |

The settings dict is passed through the dispatcher, so it belongs in the play `vars:` of
the role (as `playbooks/seb_classroom.yaml` does) or in `group_vars`, not in a task string.

```yaml
roles:
  - role: lineadicomando.win_workman.dispatcher
    vars:
      win_workman_tasks: ["seb", "seb-deploy"]
      win_workman_seb_client_settings:
        startURL: "https://classroom.google.com"
        ...
```

---

## Baseline exam lockdown

Start from this and add what the scenario needs:

```yaml
win_workman_seb_client_settings:
  startURL: "..."
  allowQuit: false
  enableLogging: true
  logDirectoryWin: 'C:\ProgramData\SafeExamBrowser\Logs'
  browserViewMode: 1               # 1 = fullscreen
  blockPopUpWindows: true
  createNewDesktop: true           # isolated Windows desktop, hides taskbar and Start
  killExplorerShell: true
  removeBrowserProfile: true       # wipe cache/profile on quit, no leakage between sessions
  allowVirtualMachine: false       # true only for VM-based test labs
  hookKeys: true                   # master switch — every key hook below needs it
  enableAltTab: false              # default is true
  enableAltCtrl: false             # default is true
  insideSebEnableStartTaskManager: false
  clipboardPolicy: 1               # Win 3.7+: block clipboard and Ctrl+C/X/V
```

The three defaults that catch people out: `enableAltTab`, `enableAltCtrl` and `enableF5`
all default to **true**. Ctrl+Alt+Del itself cannot be blocked — it is a Windows hardware
interrupt — which is why the `insideSeb*` keys exist.

### Per scenario

Moodle / LMS quiz:
```yaml
  allowBrowsingBackForward: false
  examSessionClearCookiesOnStart: true
  examSessionClearCookiesOnEnd: true
  sendBrowserExamKey: true         # Moodle validates SEB via the BEK
```

Google Classroom — allow the Google estate, block the AI assistants. In SEB URL
filtering, `action: 0` (block) wins over `action: 1` (allow) when both match:
```yaml
  URLFilterEnable: true
  URLFilterEnableContentFilter: false
  URLFilterRules:
    - { action: 1, active: true, regex: true, expression: "^https://(.*[.])?google[.]com(/.*)?$" }
    - { action: 1, active: true, regex: true, expression: "^https://(.*[.])?gstatic[.]com(/.*)$" }
    - { action: 0, active: true, regex: true, expression: "^https://gemini[.]google[.]com" }
    - { action: 0, active: true, regex: true, expression: "^https://notebooklm[.]google" }
```
`playbooks/seb_classroom.yaml` is the maintained version of this — read it before writing
a new one.

Media capture: `allowVideoCapture`, `allowAudioCapture` (Win 2.1.6+, HTML5).
Audio control: `audioControlEnabled`, `audioMute`, `audioSetVolumeLevel`,
`audioVolumeLevel` (percent, Win 2.2+).

---

## Keys effective on Windows

Defaults in parentheses; **Win only** marks keys with no Mac/iOS equivalent.

**Browser / navigation** — `startURL`, `browserViewMode` (0 window, 1 fullscreen, 2 touch),
`allowBrowsingBackForward` (false), `browserWindowAllowReload` (true), `showReloadButton`
(true), `showReloadWarning` (true), `blockPopUpWindows` (false), `enableZoomPage` (true),
`enableZoomText` (true), `zoomMode` (**Win only**, 0 page / 1 text), `allowFind` (true),
`browserWindowAllowAddressBar` (false), `enableChromeNotifications` (**Win 3.x**, false),
`allowPDFReaderToolbar` (**Win 3.x**, false), `downloadPDFFiles` (false),
`removeBrowserProfile` (**Win only**, true in 3.x), `downloadAndOpenSebConfig` (true),
`enableSebBrowser` (true — disable to use SEB as a pure kiosk launcher).

**Kiosk / desktop** — `createNewDesktop` (**Win only**, true), `killExplorerShell`
(**Win only**, false — use when `createNewDesktop` is false), `allowSwitchToApplications`
(false), `allowVirtualMachine` (false), `setVmwareConfiguration` (**Win only**),
`touchOptimized` (**Win only**), `sebServicePolicy` (**Win only**, 0 ignore / 1 warn /
2 force, default 2), `sebServiceIgnore` (**Win 3.x**), `allowScreenSharing` (RDP, false),
`allowVideoCapture` / `allowAudioCapture` (Win 2.1.6+, false).

**Keyboard hooks** — Windows only, all require `hookKeys: true` (default true):
`enableEsc` (false), `enableCtrlEsc` (false), `enableAltCtrl` (**true**), `enableAltEsc`
(false), `enableAltMouseWheel`, `enableAltTab` (**true**), `enableAltF4` (false),
`enablePrintScreen` (false), `enableRightMouse` (false), `enableStartMenu` (false),
`enableF1`–`enableF4` (false), `enableF5` (**true**), `enableF6`–`enableF12` (false).

**Ctrl+Alt+Del security screen** — Windows only, all default false:
`insideSebEnableChangeAPassword`, `insideSebEnableEaseOfAccess`,
`insideSebEnableLockThisComputer`, `insideSebEnableLogOff`, `insideSebEnableShutDown`,
`insideSebEnableStartTaskManager`, `insideSebEnableSwitchUser`,
`insideSebEnableVmWareClientShade`. The `outsideSeb*` variants restore the original
values when SEB quits.

**UI / taskbar** — `showTaskBar` (true), `taskBarHeight` (40), `showSideMenu` (true),
`showTime` (true), `showQuitButton` (Win 3.0+, true), `showBackToStartButton` (Win 3.0+,
true), `showApplicationLogButton` (false, needs `allowApplicationLog`),
`allowApplicationLog` (false), `showInputLanguage` (**Win only**, false), `allowWlan`
(**Win only**, false), `audioControlEnabled` / `audioMute` / `audioSetVolumeLevel`
(Win 2.2, false), `audioVolumeLevel` (25).

**Logging** — `enableLogging` (false), `logDirectoryWin` (**Win only**, Windows path format).

**Session / quit** — `allowQuit` (true; the spec says "currently Mac only" but it is
honoured on Windows), `hashedAdminPassword` / `hashedQuitPassword` (SHA-256 hex),
`quitURL`, `quitURLConfirm` (true), `quitURLRestart` (Win 3.1),
`examSessionClearCookiesOnStart` / `OnEnd` (Win 2.4, true),
`examSessionReconfigureAllow` (Win 3.1, false), `examSessionReconfigureConfigURL`,
`restartExamURL`, `restartExamUseStartURL` (false), `restartExamPasswordProtected` (true),
`ignoreExitKeys` (**Win only**, true), `ignoreQuitPassword` (**Win only**, false),
`exitKey1`/`2`/`3` (**Win only**, virtual key codes).

**Security / exam keys** — `clipboardPolicy` (**Win 3.7+**, 0 allow / 1 block /
2 SEB-only isolated, default 2 — replaces the removed `enablePrivateClipboard`),
`sendBrowserExamKey` (false), `configKeySalt`, `examKeySalt`, `pinEmbeddedCertificates`
(Win 2.2, false), `embeddedCertificates`, `useAsymmetricOnlyEncryption` (Win 2.2, false).

**URL filtering** — `URLFilterEnable` (false), `URLFilterEnableContentFilter` (false),
`URLFilterRules` (array of `{action, expression, regex, active}`).

**Network** — `proxySettingsPolicy` (0 system / 1 SEB), `proxies`.

**SEB Server (Win 3.1+)** — `sebMode` (0 local / 1 server / 2 VDI),
`sebServerConfiguration` (`institution`, `clientName`, `clientSecret`, `apiDiscovery`,
`pingInterval`), `sebServerURL`, `sebServerFallback`, `sebServerFallbackTimeout` (30000),
`sebServerFallbackAttempts` (5), `sebServerFallbackAttemptInterval` (2000).

**Processes** — `permittedProcesses`, `prohibitedProcesses`, `monitorProcesses` (false),
`additionalResources`.

---

## Keys with no effect on Windows — never include

| Key | Reason |
|---|---|
| `allowPreferencesWindow`, `showMenuBar`, `allowSiri`, `allowDictation`, `allowDictionaryLookup` | Mac only |
| `newBrowserWindowByLinkPolicy` | Mac/iOS only |
| `newBrowserWindowByScriptPolicy`, `allowScreenCapture`, `allowWindowCapture`, `blockScreenShotsLegacy` | Mac only |
| `allowDisplayMirroring`, `allowedDisplaysMaxNumber`, `allowedDisplayBuiltin*` | Mac only |
| `enableAAC`, `enableMacOSAAC`, `enableAppSwitcherCheck` | Mac only (`enableAAC` also deprecated) |
| `enableBrowserWindowToolbar`, `hideBrowserWindowToolbar` | Mac only |
| `enableJava`, `enableJavaScript`, `enablePlugIns`, `allowFlashFullscreen` | Mac only |
| `enablePrivateClipboard` | Win 2.3–2.4 only, **not in 3.x** — use `clipboardPolicy` |
| `enablePrivateClipboardMacEnforce`, `screenSharingMacEnforceBlocked` | Mac only |
| `logLevel`, `minMacOSVersion`, `forceAppFolderInstall`, `allowUserAppFolderInstall`, `detectStoppedProcess` | Mac only |
| `removeLocalStorage` | Mac only — use `removeBrowserProfile` |
| `copyBrowserExamKeyToClipboardWhenQuitting`, `openDownloads`, `chooseFileToUploadPolicy` | Mac only |
| `URLFilterMessage`, `URLFilterIgnoreList` | Mac / iOS only |
| `showNavigationButtons`, `showSettingsInApp`, `showScrollLockButton`, `enableScrollLock`, `enableDrawingEditor` | iOS only |
| `browserWindowShowURL`, `newBrowserWindowShowURL`, `browserMediaAutoplay`, `startURLAllowDeepLink`, `startURLAppendQueryParameter`, `mobile*` | iOS only |
| `allowUserSwitching` | Present in the spec, not implemented |
| `blacklistURLFilter`, `whitelistURLFilter`, `urlFilterRegex`, `urlFilterTrustedContent` | Windows, but deprecated XULRunner leftovers |

---

## Auditing an existing settings block

Sort each key into three buckets: effective on Windows (with its current value),
ineffective (with the reason from the table above), and worth adding for a managed school
lab. The most common real findings are a `clipboardPolicy` left at its default 2, a
missing `enableAltCtrl: false`, and an `enablePrivateClipboard` carried over from a
Windows 2.x config.
