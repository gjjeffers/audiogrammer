# Settings Persistence Design

**Date:** 2026-06-19
**Status:** Implemented

## Problem

Audiogrammer loses all user settings on every close — colors, model selection, watermark configuration, file paths, etc. Users must reconfigure everything on each launch.

## Solution

Auto-save all settings to a JSON file on window close. Auto-load on startup. Provide a "Restore Defaults" button to return to factory state.

## Storage

`~/.audiogrammer/settings.json` — user's home directory. Cross-platform, always writable, easy to locate.

## Architecture

### `core/settings.py` (new)

- `DEFAULTS` dict — canonical default for every setting
- `load() -> dict` — reads JSON file, merges with DEFAULTS so missing keys always resolve correctly
- `save(data: dict)` — writes JSON file, creates directory if needed

### `gui/app.py` additions

| Method | Purpose |
|---|---|
| `_collect_settings() -> dict` | Snapshot all tk.Vars and plain hex-color attributes into a flat dict |
| `_apply_settings(data: dict)` | Write a settings dict back to all vars; update color-picker button backgrounds |
| `on_close()` | Save settings then destroy window — registered as `WM_DELETE_WINDOW` handler |
| `_restore_defaults()` | Apply `DEFAULTS`, then pick the best available font (since `DEFAULTS["font_name"]` is `""`) |

### `main.py` change

One line: `root.protocol("WM_DELETE_WINDOW", app.on_close)` registers the save-on-close hook.

## Settings persisted

All user-facing settings: file paths (audio, background, output, watermark image), core video settings (model, font, font size, FPS, resolution, quality, review transcript flag), caption colors (text, highlight), watermark (text, position, opacity, size, color), and all waveform settings.

## Special case: font name

Font discovery runs in a background thread after `__init__`. The saved `font_name` is stored as `_pending_font_name` and applied inside `_on_fonts_loaded` once the font list is ready. If the saved font is no longer available, the app falls back to its default font selection logic.

## UI

"Restore Defaults" button sits in the Generate/Cancel row: `[ Generate Audiogram ] [ Cancel ] [ Restore Defaults ]`. No confirmation dialog — the action is immediately reversible.
