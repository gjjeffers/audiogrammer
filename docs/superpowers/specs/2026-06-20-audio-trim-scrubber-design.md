# Audio Trim Scrubber — Design

**Date:** 2026-06-20
**Status:** Approved for planning

## Problem

Audiogrammer currently transcribes and renders the **entire** audio file. The core
podcaster use case, though, is pulling a 30–90 second highlight out of a 45-minute
episode. Without in/out trim points, the user must pre-cut the clip in another tool
before opening Audiogrammer — which kills the "single tool" value proposition.

## Goal

Add an in/out trim selector so a user can pick a highlight window directly in
Audiogrammer. Trimming must happen **before transcription**, so Whisper processes
only the selected window (e.g. 60 seconds) instead of the whole episode — an
order-of-magnitude speedup, not just a convenience.

## Decisions (locked during brainstorming)

1. **Finding the clip:** visual waveform + numeric mm:ss entry. **No audio playback**
   (keeps scope tight; tkinter has no native audio and we add no new dependency).
2. **UI placement:** a separate **"Trim Audio…"** modal dialog, mirroring the existing
   `WaveformSettingsDialog` pattern. Keeps the main window compact; a status label
   shows `(full)` or the selected range.
3. **Precision model:** **overview + detail.** A full-file overview strip for coarse
   selection, plus a zoomed detail strip at each handle for fine placement, with
   mm:ss fields alongside. All three representations stay in sync.
4. **Pipeline (Approach A):** trim **before** transcription by slicing the decoded
   audio sample array; the render subclips the audio to the same window.

## Architecture

### New / changed files

| File | Change |
|---|---|
| `core/waveform.py` | Add `compute_overview(audio_or_path, buckets) -> (np.ndarray, float)` returning a 0..1 peak envelope plus duration. Generalizes the existing "progress" mode envelope so the render-time waveform and the trim dialog share one code path. |
| `core/trim.py` | **New.** Pure helpers, independently testable: `slice_audio(array, sr, start, end)`, `clamp_range(start, end, duration, min_len)`, `format_timecode(seconds)` / `parse_timecode(text)`. |
| `gui/trim_dialog.py` | **New.** `TrimDialog(tk.Toplevel)` modal: `transient`, `grab_set`, edits the app's shared trim tk.Vars in place (same pattern as `WaveformSettingsDialog`). |
| `core/transcriber.py` | `transcribe(..., trim_start=None, trim_end=None)`. When set, decode via `whisper.load_audio()`, slice the sample array, transcribe the slice (0-relative timestamps). |
| `core/composer.py` | `compose_video(..., trim_start=None, trim_end=None)`. After `AudioFileClip(...)`, subclip to the window so duration, frames, and the reactive waveform all operate on it. |
| `gui/app.py` | Add trim state vars, a **Trim Audio…** button + status label, thread trim params into `transcribe()`/`compose_video()`, reset trim when a new audio file is loaded. |
| `core/settings.py` | Add `trim_enabled`, `trim_start`, `trim_end` to `DEFAULTS` + collect/apply. |

### Data flow (Generate)

```
audio file ──► [TrimDialog sets trim_enabled / trim_start / trim_end on app vars]
                       │
   Generate ──► transcribe(path, trim_start, trim_end)   # Whisper runs on the slice only
                       │  segments (0-relative)
                       ▼
            compose_video(..., trim_start, trim_end)      # audio subclipped to window
                       │  background loops to fill the (shorter) duration
                       ▼                                   # reactive waveform analyzes window
                   output.mp4
```

The overview envelope is computed **lazily when the dialog opens** (background thread,
"Analyzing…" state), cached per audio path so reopening is instant. It does **not**
block audio selection in the main window.

## Pipeline detail

### Transcription (`core/transcriber.py`)

```python
def transcribe(audio_path, model_size="base", status_callback=None,
               trim_start=None, trim_end=None):
    import whisper
    model = whisper.load_model(model_size)
    if trim_start is not None and trim_end is not None and trim_end > trim_start:
        sr = whisper.audio.SAMPLE_RATE          # 16000
        samples = whisper.load_audio(audio_path)  # whole file, fast ffmpeg decode
        samples = slice_audio(samples, sr, trim_start, trim_end)  # core/trim.py
        result = model.transcribe(samples, word_timestamps=True)
    else:
        result = model.transcribe(audio_path, word_timestamps=True)
    # ... existing segment-building unchanged; timestamps are clip-relative ...
```

`slice_audio` is a pure function (`array[int(start*sr):int(end*sr)]` with clamping) so
the index math is unit-tested without invoking Whisper.

### Composition (`core/composer.py`)

```python
audio = AudioFileClip(audio_path)
if trim_start is not None and trim_end is not None and trim_end > trim_start:
    sub = getattr(audio, "subclipped", None) or audio.subclip   # moviepy v2 / v1
    audio = sub(trim_start, trim_end)
duration = audio.duration   # now the trimmed duration
```

Everything downstream already keys off `audio.duration`, so total frames, the reactive
waveform analysis, and background looping all adapt automatically. Segments from the
trimmed transcription are 0-relative and line up with the subclipped audio.

## Trim dialog UX (`gui/trim_dialog.py`)

Modal `Toplevel`, non-resizable, mirrors `WaveformSettingsDialog`.

- **Overview strip** — full width (~560px), ~90px tall. Draws the peak envelope; a
  shaded selection rectangle between the in/out handles; regions outside the selection
  dimmed. Two draggable handle lines (in = left, out = right).
- **Detail strips** — two zoomed canvases (In detail, Out detail), each ~270px wide,
  ~70px tall, showing ±~3s around their handle (~0.02 s/px — ample precision), each with
  its own draggable handle.
- **Numeric fields** — In and Out as `m:ss.s`, each with nudge buttons (−1s, −0.1s,
  +0.1s, +1s). Two-way synced with the handles.
- **Readout** — `Selection: 1:03.4  (of 45:12.0)`.
- **Buttons** — `Use Full Audio` (clears `trim_enabled`, resets to 0..duration) and
  `Close`.
- **On open** — if the envelope for the current audio path isn't cached, show
  "Analyzing…" and compute on a background thread, populating when ready. If no audio
  file is selected, show a message and disable the controls.

### State sync

The dialog edits the app's shared vars: `trim_enabled` (BooleanVar), `trim_start`
(DoubleVar, seconds), `trim_end` (DoubleVar). The overview handle, detail handles, and
numeric fields all read/write the *same* vars, with canvas redraws on var traces —
so the three representations stay in sync automatically. Setting any selection sets
`trim_enabled = True`; `Use Full Audio` sets it `False`.

## Main window (`gui/app.py`)

Add a row (grouped with the existing waveform launcher row): a **Trim Audio…** button
and a status label. The status updates via a trace on the trim vars — `(full)` in grey
when disabled, else `(0:12.0 – 1:15.0)` in green. `_open_trim_dialog` constructs
`TrimDialog`, matching `_open_waveform_settings`.

In `_worker`, pass `trim_start=self.trim_start.get() if self.trim_enabled.get() else None`
(and the same for `trim_end`) into **both** `transcribe()` and `compose_video()`.

## State, persistence, edge cases

- **New audio file selected** → reset `trim_enabled=False`, `trim_start=0`, `trim_end=0`;
  status shows `(full)`. (Trim points are file-specific; carrying them to a different
  file would be wrong.)
- **Persistence** — add `trim_enabled` (False), `trim_start` (0.0), `trim_end` (0.0) to
  `settings.DEFAULTS` and to collect/apply. On startup the saved `audio_path` is also
  restored, so restoring its trim is consistent.
- **Clamping** (`clamp_range`) — keep `0 <= start < end <= duration` and enforce a
  minimum selection length (0.5s). Handles can't cross.
- **Validation** — `_generate` guards that, when `trim_enabled`, `end > start`
  (defensive; clamping should already guarantee it).
- **Duration source** — captured from the overview analysis and stored on the app
  (`self._audio_duration`) for clamping and the readout.

## Testing

Focus on pure functions; tkinter UI is verified manually.

- `core/trim.py`
  - `slice_audio` — known array + sr, assert slice indices/length; clamps out-of-range.
  - `clamp_range` — crossing handles, min-length enforcement, bounds.
  - `format_timecode` / `parse_timecode` — round-trip and edge values.
- `core/waveform.py::compute_overview` — synthetic signal → envelope shape == buckets,
  values in 0..1, a louder region maps to higher buckets; duration is correct.
- `core/transcriber.py` — mock `whisper.load_audio` to return a known array; assert the
  sliced array handed to `model.transcribe` matches the expected window.
- `core/composer.py` — light: mock `AudioFileClip` and assert `subclipped`/`subclip`
  is called with the right args when trim is set, and not called when it isn't.
- **Manual integration** — load a long file, trim a ~60s window, Generate; confirm the
  output duration ≈ the selection, captions align, and transcription is fast.

## Out of scope (YAGNI)

- Audio playback / scrubbing-to-hear.
- Multiple trim regions or a stitched multi-clip export.
- Waveform zoom/pan beyond the fixed overview + detail strips.
- Persisting trim per-file across different files.
