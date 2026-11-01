# Changelog

## 1.9.13 – 2026-11-01

- **Input source names are recalled.** On the Wing a channel without its own name shows the name of the input
  source it is patched to, and in most shows that is where the names live. They were stored in every cue but
  never sent back, so a cue could not change the names on the console. New switch in Recall Scope →
  **Console Config → Input source names** (on by default, also for cues in existing show files).
- Self-test: source names are part of the "values in = values out" check, and the switch is tested on/off.

## 1.9.12 – 2026-11-01

- **Values keep their exact type and value from Wing to Wing.** libwing printed a whole-number float without a
  decimal point (a fader at exactly 0 dB came out as "0"), so it was stored – and recalled – as an *integer*.
  wingmon now always sends floats with a decimal point, the app knows that faders, send/main levels and float
  enums are floats, and values from older show files are sent as floats again where the console expects one.
- Floats are sent with full precision (e.g. 1234.567 Hz is no longer rounded to 1234.57).
- Self-test: "values in = values out" – lines exactly as wingmon prints them go through the app's parser, a cue
  and a recall, and must come out unchanged; the bundled wingmon then encodes them (new `--encode-test` mode)
  and the bytes for the Wing are decoded and checked for the same value and type.
- macOS: wingmon is bundled as `wingmon` again (it was bundled as `wingmon-macos` together with the Rust
  sources, and only found through a fallback). The self-test now insists on the right name.
- GitHub Actions updated to their Node 24 versions.

## 1.9.11 – 2026-11-01

**New (both can be switched on/off, saved with the show)**
- **Auto-reconnect** (connection bar, on by default): if the connection to the Wing is lost unexpectedly, the app
  tries again every 5 seconds and syncs by itself; GO unlocks when the sync is complete. Never after a manual
  Disconnect. The Connect button shows *Stop* while it is trying.
- **Backups** (toolbar, on by default): every save, including autosave, keeps the previous version in
  `<show name> backups/` next to the show file, named with date and time. The newest 30 are kept; identical
  versions are skipped. A failing backup never stops the save itself.
- Pressing Connect while an earlier attempt is still running no longer leaves a second wingmon running.

**Windows**
- New installer (`WingTheatreController-windows-installer.zip` → `WingTheatreController-Setup.exe`, signed):
  install for all users or only you, Start menu entry, optional desktop icon, uninstaller, double-click a
  `.wts` to open it, and (all-users install) a Windows Firewall rule for OSC/Companion remote control.
- The portable version stays: `WingTheatreController-windows-portable.zip`.
- Every `.exe`, `.dll` and `.pyd` is signed (Azure Artifact Signing), so Smart App Control lets the app start.

**Recall and fades (fixes)**
- wingmon sent whole numbers 64–127 as a single byte, which Wing reads as a *node index*, not a value – such
  integer parameters were never recalled. They are now sent as proper int16/int32 values.
- A data byte 0xdf (inside a hash, number or text) was not escaped correctly, so Wing could read it as a
  channel switch and drop up to three following parameters in the same burst. All data is now escaped as the
  Wing protocol requires.
- A fade down into mute muted the channel at the *start* of the fade, so the fade was not heard. The mute now
  comes at the end of the fade.
- That end-of-fade mute could still fire after a new GO (seconds later, muting a channel the new cue had
  brought up). It is now cancelled by a new GO, and applied at once by Cancel fade.
- The recall thread and the fade timer could write to wingmon at the same moment and mix two commands into one
  line. All writes now go through one lock.
- Names and texts containing a comma are recalled intact (the parameter separator is no longer a comma).
- Clicking an individual bus/matrix send in Recall Scope raised an internal error, so the change did not mark
  the show as changed (no autosave / save prompt) and some circles were not refreshed.
- wingmon no longer hangs at 100 % CPU if the Wing stops answering during the initial sync; the app sees the
  disconnect instead.

**Companion / remote**
- New command `CANCEL_FADE` (TCP) and `/wingtheatre/cancelfade` (OSC).
- `fading` is now sent live when a fade starts and ends, plus `fade_remaining` (seconds left).
- SNAP_GO by part of a name only fires when it matches exactly one cue.
- Companion module 1.1: Cancel fade action + preset, `fade_remaining` variable, default port 9001 (matches the
  app), shows "server full" when 4 Companions are already connected, closes its old connection properly on
  reconnect/config change, TCP keep-alive.

**Other**
- Log files moved to the user's own folder (macOS `~/Library/Logs/Wing Theatre Controller`, Windows
  `%LOCALAPPDATA%\Wing Theatre Controller\Logs`) – writing next to the app would break the macOS signature and
  fails under Program Files. *? → Open log folder*. Logs over 5 MB are rotated. Errors in background threads
  are logged too.
- Double-clicking a `.wts` in Finder opens it (macOS); a `.wts` on the command line is opened at start.
- Built apps run a self-test in GitHub Actions (start, recall, fades, save/load, Companion server, bundled
  wingmon/propmap) on macOS, Windows and the installed Windows version before anything is released.
- libwing is pinned to a tested commit (1.0.6, includes upstream's set_int fix); PyQt6 and PyInstaller are kept
  within their current major versions.
- wingmon no longer logs every fade tick.

## 1.9.10 – 2026-11-01
- Windows build signed with Azure Artifact Signing.

## 1.9.9 – 2026-10-24
- Companion TCP server accepts up to 4 connections at the same time.

## 1.9.8 – 2026-10-24
- macOS build signed with Developer ID and notarised by Apple.
