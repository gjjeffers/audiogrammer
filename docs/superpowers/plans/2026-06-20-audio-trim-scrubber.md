# Audio Trim Scrubber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user pick an in/out highlight window in a "Trim Audio…" dialog so Whisper transcribes and the renderer encodes only the selected window, not the whole episode.

**Architecture:** Trim happens *before* transcription — the decoded audio sample array is sliced and only that window is transcribed (0-relative timestamps); the renderer subclips the audio to the same window. A modal `TrimDialog` (mirroring the existing `WaveformSettingsDialog`) edits three shared `tk.Var`s on the app (`trim_enabled`, `trim_start`, `trim_end`). All numeric/handle math lives in pure, unit-tested helpers in `core/trim.py`; the overview envelope reuses a generalized `compute_overview` in `core/waveform.py`.

**Tech Stack:** Python 3.12, tkinter/ttk, OpenAI Whisper, moviepy 2.x, Pillow, numpy. Tests via pytest (dev-only).

## Global Constraints

- **No new runtime dependencies.** No audio playback. pytest is dev-only (`requirements-dev.txt`).
- **moviepy is v2** — use `audio.subclipped(start, end)` (NOT `subclip`).
- **Whisper sample rate** — use `whisper.audio.SAMPLE_RATE` (16000), never a hardcoded literal in production code.
- **Trim is before transcription.** Segment timestamps are clip-relative (start at 0); the renderer subclips to the same window so they align.
- **Trim points are file-specific** — reset trim (`trim_enabled=False`, `trim_start=0`, `trim_end=0`) whenever a new audio file is selected.
- **Minimum selection length:** 0.5s. Selection always stays within `[0, duration]`; handles cannot cross.
- **Dialog pattern:** match `gui/waveform_settings.py` — `Toplevel`, `transient(parent)`, `grab_set()`, edits the app's shared vars in place.
- **Status label:** `(full)` in grey `#888888` when disabled, else `(m:ss.s – m:ss.s)` in green `#2e7d32`.
- **Run tests from the repo root** with `python -m pytest` so `core` / `gui` are importable.

---

### Task 1: Pure trim helpers + test infrastructure

**Files:**
- Create: `requirements-dev.txt`
- Create: `core/trim.py`
- Test: `tests/test_trim.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `slice_audio(samples: np.ndarray, sr: int, start: float, end: float) -> np.ndarray`
  - `clamp_range(start: float, end: float, duration: float, min_len: float = 0.5) -> tuple[float, float]`
  - `format_timecode(seconds: float) -> str` (`63.4 -> "1:03.4"`)
  - `parse_timecode(text: str) -> float | None`
  - `should_trim(trim_start, trim_end) -> bool`
  - `apply_trim(audio, trim_start, trim_end)` — returns `audio.subclipped(start, end)` when valid, else `audio`

- [ ] **Step 1: Create dev requirements and install pytest**

Create `requirements-dev.txt`:

```
pytest>=8.0
```

Run: `python -m pip install -r requirements-dev.txt`
Expected: pytest installs successfully.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_trim.py`:

```python
import numpy as np
import pytest

from core.trim import (
    slice_audio,
    clamp_range,
    format_timecode,
    parse_timecode,
    should_trim,
    apply_trim,
)


def test_slice_audio_basic_window():
    samples = np.arange(1000, dtype=np.float32)
    out = slice_audio(samples, sr=100, start=2.0, end=5.0)
    assert len(out) == 300
    assert out[0] == 200.0


def test_slice_audio_clamps_to_bounds():
    samples = np.arange(100, dtype=np.float32)
    out = slice_audio(samples, sr=10, start=-5.0, end=999.0)
    assert len(out) == 100


def test_slice_audio_empty_when_end_before_start():
    samples = np.arange(100, dtype=np.float32)
    out = slice_audio(samples, sr=10, start=5.0, end=2.0)
    assert len(out) == 0


def test_clamp_range_within_bounds_unchanged():
    assert clamp_range(2.0, 8.0, duration=10.0) == (2.0, 8.0)


def test_clamp_range_clips_to_duration():
    start, end = clamp_range(-3.0, 99.0, duration=10.0)
    assert start == 0.0
    assert end == 10.0


def test_clamp_range_uncrosses_handles():
    start, end = clamp_range(8.0, 2.0, duration=10.0)
    assert start < end


def test_clamp_range_enforces_min_length():
    start, end = clamp_range(5.0, 5.1, duration=10.0, min_len=0.5)
    assert round(end - start, 6) >= 0.5


def test_clamp_range_min_length_near_end_pushes_start_in():
    start, end = clamp_range(9.9, 10.0, duration=10.0, min_len=0.5)
    assert end == 10.0
    assert round(end - start, 6) == 0.5


def test_format_timecode():
    assert format_timecode(63.4) == "1:03.4"
    assert format_timecode(0.0) == "0:00.0"
    assert format_timecode(5.25) == "0:05.2"


def test_parse_timecode_roundtrip():
    assert parse_timecode("1:03.4") == pytest.approx(63.4)
    assert parse_timecode("75") == pytest.approx(75.0)
    assert parse_timecode("0:05") == pytest.approx(5.0)


def test_parse_timecode_invalid_returns_none():
    assert parse_timecode("") is None
    assert parse_timecode("abc") is None


def test_should_trim():
    assert should_trim(1.0, 3.0) is True
    assert should_trim(None, 3.0) is False
    assert should_trim(3.0, 3.0) is False
    assert should_trim(5.0, 2.0) is False


class _FakeAudio:
    def __init__(self):
        self.calls = []

    def subclipped(self, start, end):
        self.calls.append((start, end))
        return "SUBCLIPPED"


def test_apply_trim_invokes_subclipped_when_valid():
    audio = _FakeAudio()
    result = apply_trim(audio, 2.0, 5.0)
    assert result == "SUBCLIPPED"
    assert audio.calls == [(2.0, 5.0)]


def test_apply_trim_passthrough_when_no_trim():
    audio = _FakeAudio()
    result = apply_trim(audio, None, None)
    assert result is audio
    assert audio.calls == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_trim.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.trim'`.

- [ ] **Step 4: Implement `core/trim.py`**

```python
"""Pure helpers for the audio trim feature — no tkinter, no I/O."""
from __future__ import annotations

import numpy as np


def slice_audio(samples: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    """Return the [start, end] second window of a mono sample array.

    Indices are clamped to the array bounds. If ``end <= start`` the result is empty.
    """
    a = max(0, int(round(start * sr)))
    b = min(len(samples), int(round(end * sr)))
    if b <= a:
        return samples[0:0]
    return samples[a:b]


def clamp_range(start: float, end: float, duration: float, min_len: float = 0.5) -> tuple[float, float]:
    """Clamp a selection to [0, duration], uncrossing handles and enforcing min length."""
    duration = max(0.0, float(duration))
    min_len = min(min_len, duration)
    start = min(max(0.0, float(start)), duration)
    end = min(max(0.0, float(end)), duration)
    if end < start:
        start, end = end, start
    if end - start < min_len:
        end = min(duration, start + min_len)
        start = max(0.0, end - min_len)
    return start, end


def format_timecode(seconds: float) -> str:
    """Format seconds as ``m:ss.s`` (e.g. 63.4 -> '1:03.4')."""
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    rem = seconds - minutes * 60
    return f"{minutes}:{rem:04.1f}"


def parse_timecode(text: str) -> float | None:
    """Parse ``m:ss.s`` or plain seconds into a float. Return None if unparseable."""
    text = text.strip()
    if not text:
        return None
    try:
        if ":" in text:
            mins, secs = text.split(":", 1)
            return int(mins) * 60 + float(secs)
        return float(text)
    except ValueError:
        return None


def should_trim(trim_start, trim_end) -> bool:
    """True when both bounds are set and describe a non-empty window."""
    return trim_start is not None and trim_end is not None and trim_end > trim_start


def apply_trim(audio, trim_start, trim_end):
    """Return ``audio`` subclipped to the window, or unchanged if no valid trim.

    ``audio`` is any object exposing moviepy v2's ``subclipped(start, end)``.
    """
    if should_trim(trim_start, trim_end):
        return audio.subclipped(trim_start, trim_end)
    return audio
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_trim.py -v`
Expected: PASS — all tests green.

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt core/trim.py tests/test_trim.py
git commit -m "Add pure trim helpers and pytest dev setup"
```

---

### Task 2: Overview envelope in core/waveform.py

**Files:**
- Modify: `core/waveform.py` (add `compute_overview`, `load_audio_overview`; refactor the `progress` branch of `analyze_audio` to reuse `compute_overview`)
- Test: `tests/test_waveform_overview.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `compute_overview(mono: np.ndarray, buckets: int) -> np.ndarray` — peak envelope normalized to 0..1 (length == buckets)
  - `load_audio_overview(audio_path: str, buckets: int = 600, _loader=None, _sample_rate=16000) -> tuple[np.ndarray, float]` — returns `(envelope, duration_seconds)`; when `_loader` is None it decodes via `whisper.load_audio`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_waveform_overview.py`:

```python
import numpy as np

from core.waveform import compute_overview, load_audio_overview


def test_compute_overview_length_and_range():
    rng = np.linspace(-1.0, 1.0, 10000, dtype=np.float64)
    env = compute_overview(rng, buckets=50)
    assert env.shape == (50,)
    assert env.min() >= 0.0
    assert env.max() <= 1.0


def test_compute_overview_louder_region_is_higher():
    quiet = np.full(5000, 0.1, dtype=np.float64)
    loud = np.full(5000, 0.9, dtype=np.float64)
    mono = np.concatenate([quiet, loud])
    env = compute_overview(mono, buckets=2)
    assert env[1] > env[0]
    assert env[1] == 1.0  # peak-normalized


def test_compute_overview_empty_signal():
    env = compute_overview(np.array([], dtype=np.float64), buckets=8)
    assert env.shape == (8,)
    assert env.max() == 0.0


def test_load_audio_overview_uses_injected_loader():
    samples = np.concatenate([
        np.full(16000, 0.2, dtype=np.float32),   # 1s quiet
        np.full(16000, 0.8, dtype=np.float32),   # 1s loud
    ])
    captured = {}

    def fake_loader(path):
        captured["path"] = path
        return samples

    env, duration = load_audio_overview(
        "episode.mp3", buckets=2, _loader=fake_loader, _sample_rate=16000
    )
    assert captured["path"] == "episode.mp3"
    assert duration == 2.0
    assert env.shape == (2,)
    assert env[1] > env[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_waveform_overview.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_overview'`.

- [ ] **Step 3: Add `compute_overview` and `load_audio_overview` to `core/waveform.py`**

Add these functions near the top of the "Audio analysis" section (after `_normalize`, before `analyze_audio`):

```python
def compute_overview(mono: np.ndarray, buckets: int) -> np.ndarray:
    """Peak-envelope of a mono signal across ``buckets`` buckets, normalized to 0..1."""
    mono = np.asarray(mono, dtype=np.float64)
    buckets = max(1, int(buckets))
    n = mono.size
    if n == 0:
        return np.zeros(buckets, dtype=np.float64)
    env = np.zeros(buckets, dtype=np.float64)
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    absmono = np.abs(mono)
    for i in range(buckets):
        a, b = edges[i], edges[i + 1]
        if b > a:
            env[i] = absmono[a:b].max()
    peak = float(env.max())
    if peak <= 1e-9:
        return np.zeros(buckets, dtype=np.float64)
    return env / peak


def load_audio_overview(audio_path, buckets: int = 600, _loader=None, _sample_rate: int = 16000):
    """Decode ``audio_path`` to mono and return (envelope 0..1, duration_seconds).

    ``_loader`` / ``_sample_rate`` are injection seams for tests; in production they
    resolve to ``whisper.load_audio`` and ``whisper.audio.SAMPLE_RATE``.
    """
    if _loader is None:
        import whisper
        _loader = whisper.load_audio
        _sample_rate = whisper.audio.SAMPLE_RATE
    samples = _loader(audio_path)
    duration = len(samples) / float(_sample_rate)
    return compute_overview(samples, buckets), duration
```

- [ ] **Step 4: Refactor the `progress` branch of `analyze_audio` to reuse `compute_overview`**

In `analyze_audio`, replace the existing progress block:

```python
    if config.mode == "progress":
        # Peak envelope across bar_count buckets over the whole track.
        env = np.zeros(bars, dtype=np.float64)
        edges = np.linspace(0, n, bars + 1, dtype=int)
        absmono = np.abs(mono)
        for i in range(bars):
            a, b = edges[i], edges[i + 1]
            if b > a:
                env[i] = absmono[a:b].max()
        return _normalize(env, config.sensitivity)
```

with:

```python
    if config.mode == "progress":
        # Peak envelope across bar_count buckets over the whole track.
        env = compute_overview(mono, bars)
        return np.clip(env * config.sensitivity, 0.0, 1.0)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_waveform_overview.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/waveform.py tests/test_waveform_overview.py
git commit -m "Add overview envelope helpers, reuse in progress waveform"
```

---

### Task 3: Trim-before-transcription in core/transcriber.py

**Files:**
- Modify: `core/transcriber.py` (`transcribe` signature + slicing)
- Test: `tests/test_transcriber_trim.py`

**Interfaces:**
- Consumes: `core.trim.slice_audio` (Task 1).
- Produces: `transcribe(audio_path, model_size="base", status_callback=None, trim_start=None, trim_end=None) -> List[Segment]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_transcriber_trim.py`:

```python
import sys
import types

import numpy as np


def _install_fake_whisper(monkeypatch, captured):
    fake = types.ModuleType("whisper")
    fake.audio = types.SimpleNamespace(SAMPLE_RATE=16000)
    fake.load_audio = lambda path: np.arange(16000 * 10, dtype=np.float32)  # 10s

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            captured["audio"] = audio
            captured["kwargs"] = kwargs
            return {"segments": []}

    fake.load_model = lambda size: FakeModel()
    monkeypatch.setitem(sys.modules, "whisper", fake)


def test_transcribe_slices_audio_window(monkeypatch):
    captured = {}
    _install_fake_whisper(monkeypatch, captured)
    from core.transcriber import transcribe

    transcribe("episode.mp3", model_size="base", trim_start=2.0, trim_end=5.0)

    # 3 seconds of a 16kHz stream
    assert len(captured["audio"]) == 3 * 16000
    assert captured["audio"][0] == 2 * 16000


def test_transcribe_no_trim_passes_path(monkeypatch):
    captured = {}
    _install_fake_whisper(monkeypatch, captured)
    from core.transcriber import transcribe

    transcribe("episode.mp3", model_size="base")

    assert captured["audio"] == "episode.mp3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transcriber_trim.py -v`
Expected: FAIL — `transcribe()` doesn't accept `trim_start` / always passes the path.

- [ ] **Step 3: Modify `transcribe` in `core/transcriber.py`**

Update the imports and signature, and branch on trim. Replace the top of the function (from `import whisper` through the `result = model.transcribe(...)` line):

```python
def transcribe(
    audio_path: str,
    model_size: str = "base",
    status_callback: Optional[Callable[[str], None]] = None,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
) -> List[Segment]:
    import whisper

    from core.trim import should_trim, slice_audio

    if status_callback:
        status_callback(f"Loading Whisper model '{model_size}'...")

    model = whisper.load_model(model_size)

    if status_callback:
        status_callback("Transcribing audio (this may take a moment)...")

    if should_trim(trim_start, trim_end):
        sr = whisper.audio.SAMPLE_RATE
        samples = whisper.load_audio(audio_path)
        samples = slice_audio(samples, sr, trim_start, trim_end)
        result = model.transcribe(samples, word_timestamps=True)
    else:
        result = model.transcribe(audio_path, word_timestamps=True)
```

Leave the segment-building loop below unchanged. Add `Optional` to the existing `from typing import` line if not already imported (it imports `Optional` already).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transcriber_trim.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/transcriber.py tests/test_transcriber_trim.py
git commit -m "Transcribe only the trimmed audio window"
```

---

### Task 4: Subclip the rendered audio in core/composer.py

**Files:**
- Modify: `core/composer.py` (`compose_video` signature + `apply_trim` call)
- Test: `tests/test_composer_trim.py`

**Interfaces:**
- Consumes: `core.trim.apply_trim` (Task 1).
- Produces: `compose_video(..., trim_start=None, trim_end=None)` — adds two keyword params after `progress_callback`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_composer_trim.py`. This patches the moviepy import and the background loader so only the trim wiring is exercised:

```python
import sys
import types

import numpy as np
from PIL import Image

import core.composer as composer


class _FakeAudio:
    def __init__(self):
        self.duration = 100.0
        self.subclipped_calls = []
        self.closed = False

    def subclipped(self, start, end):
        self.subclipped_calls.append((start, end))
        sub = _FakeAudio()
        sub.duration = end - start
        return sub

    def close(self):
        self.closed = True


class _FakeClip:
    def with_fps(self, fps):
        return self

    def with_audio(self, audio):
        return self

    def write_videofile(self, *args, **kwargs):
        pass


def _patch_pipeline(monkeypatch, fake_audio):
    fake_moviepy = types.ModuleType("moviepy")
    fake_moviepy.AudioFileClip = lambda path: fake_audio
    fake_moviepy.VideoClip = lambda make_frame, duration=None: _FakeClip()
    monkeypatch.setitem(sys.modules, "moviepy", fake_moviepy)

    frame = Image.new("RGBA", (32, 32), (0, 0, 0, 255))
    monkeypatch.setattr(
        composer, "_load_background", lambda *a, **k: ((lambda t: frame), (lambda: None))
    )


def test_compose_video_subclips_when_trim_set(monkeypatch):
    fake_audio = _FakeAudio()
    _patch_pipeline(monkeypatch, fake_audio)

    composer.compose_video(
        bg_path="bg.png",
        audio_path="a.mp3",
        segments=[],
        output_path="out.mp4",
        trim_start=10.0,
        trim_end=70.0,
    )

    assert fake_audio.subclipped_calls == [(10.0, 70.0)]


def test_compose_video_no_subclip_without_trim(monkeypatch):
    fake_audio = _FakeAudio()
    _patch_pipeline(monkeypatch, fake_audio)

    composer.compose_video(
        bg_path="bg.png",
        audio_path="a.mp3",
        segments=[],
        output_path="out.mp4",
    )

    assert fake_audio.subclipped_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_composer_trim.py -v`
Expected: FAIL — `compose_video()` got an unexpected keyword argument `trim_start`.

- [ ] **Step 3: Modify `compose_video` in `core/composer.py`**

Add the import at the top of the file (with the other `from core...` imports):

```python
from core.trim import apply_trim
```

Add the two parameters to the signature (after `progress_callback`):

```python
    progress_callback: Optional[Callable[[float], None]] = None,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
) -> None:
```

Then, right after the audio is loaded, subclip it. Replace:

```python
    audio = AudioFileClip(audio_path)
    duration = audio.duration
```

with:

```python
    audio = AudioFileClip(audio_path)
    audio = apply_trim(audio, trim_start, trim_end)
    duration = audio.duration
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_composer_trim.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite so far**

Run: `python -m pytest -v`
Expected: PASS — all tests from Tasks 1-4 green.

- [ ] **Step 6: Commit**

```bash
git add core/composer.py tests/test_composer_trim.py
git commit -m "Subclip rendered audio to the trim window"
```

---

### Task 5: Persist trim settings in core/settings.py

**Files:**
- Modify: `core/settings.py` (`DEFAULTS`)
- Test: `tests/test_settings_trim.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DEFAULTS` gains `trim_enabled` (False), `trim_start` (0.0), `trim_end` (0.0).

- [ ] **Step 1: Write the failing test**

Create `tests/test_settings_trim.py`:

```python
import core.settings as settings


def test_defaults_include_trim_keys():
    assert settings.DEFAULTS["trim_enabled"] is False
    assert settings.DEFAULTS["trim_start"] == 0.0
    assert settings.DEFAULTS["trim_end"] == 0.0


def test_load_fills_trim_defaults(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "_SETTINGS_FILE", f)
    loaded = settings.load()
    assert loaded["trim_enabled"] is False
    assert loaded["trim_start"] == 0.0
    assert loaded["trim_end"] == 0.0


def test_save_then_load_roundtrips_trim(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "_SETTINGS_FILE", f)
    data = dict(settings.DEFAULTS)
    data.update(trim_enabled=True, trim_start=12.5, trim_end=72.0)
    settings.save(data)
    loaded = settings.load()
    assert loaded["trim_enabled"] is True
    assert loaded["trim_start"] == 12.5
    assert loaded["trim_end"] == 72.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_settings_trim.py -v`
Expected: FAIL — `KeyError: 'trim_enabled'`.

- [ ] **Step 3: Add trim keys to `DEFAULTS`**

In `core/settings.py`, add after the `# Waveform` block (before the closing `}` of `DEFAULTS`):

```python
    # Trim
    "trim_enabled": False,
    "trim_start": 0.0,
    "trim_end": 0.0,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_settings_trim.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/settings.py tests/test_settings_trim.py
git commit -m "Persist trim settings"
```

---

### Task 6: Wire trim state into gui/app.py

**Files:**
- Modify: `gui/app.py`

**Interfaces:**
- Consumes: `core.trim.format_timecode` (Task 1); `transcribe(..., trim_start, trim_end)` (Task 3); `compose_video(..., trim_start, trim_end)` (Task 4); settings trim keys (Task 5).
- Produces (consumed by Task 7's `TrimDialog`):
  - `self.trim_enabled: tk.BooleanVar`, `self.trim_start: tk.DoubleVar`, `self.trim_end: tk.DoubleVar`
  - `self._audio_duration: float` (0.0 until known)
  - `self._overview_cache: dict[str, tuple[np.ndarray, float]]`
  - method `_open_trim_dialog(self)`

This task is GUI code; verification is the manual checklist in Step 7 (the codebase has no automated GUI tests). All math it touches is already unit-tested in Tasks 1-5.

- [ ] **Step 1: Add trim state vars**

In `__init__`, right after the waveform state block (after `self.wf_gradient_color = "#00BFFF"`), add:

```python
        # Trim state (edited via the Trim Audio dialog)
        self.trim_enabled = tk.BooleanVar(value=False)
        self.trim_start = tk.DoubleVar(value=0.0)
        self.trim_end = tk.DoubleVar(value=0.0)
        self._audio_duration = 0.0
        self._overview_cache: dict = {}
```

- [ ] **Step 2: Add the Trim Audio launcher row**

In `_build_ui`, immediately after the `files` LabelFrame block (after `files.columnconfigure(1, weight=1)`), add:

```python
        # ---- Trim launcher ----------------------------------------------
        trim_row = ttk.Frame(root_frame)
        trim_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(trim_row, text="Trim Audio…", command=self._open_trim_dialog).pack(side=tk.LEFT)
        self._trim_status_label = ttk.Label(trim_row, text="(full)", foreground="#888888")
        self._trim_status_label.pack(side=tk.LEFT, padx=(8, 0))
        self.trim_enabled.trace_add("write", self._update_trim_status)
        self.trim_start.trace_add("write", self._update_trim_status)
        self.trim_end.trace_add("write", self._update_trim_status)
```

- [ ] **Step 3: Add the status updater and dialog opener**

Add these methods near `_update_wf_status` / `_open_waveform_settings`:

```python
    def _open_trim_dialog(self) -> None:
        from gui.trim_dialog import TrimDialog
        TrimDialog(self.root, self)

    def _update_trim_status(self, *_) -> None:
        from core.trim import format_timecode
        if self.trim_enabled.get():
            text = f"({format_timecode(self.trim_start.get())} – {format_timecode(self.trim_end.get())})"
            self._trim_status_label.config(text=text, foreground="#2e7d32")
        else:
            self._trim_status_label.config(text="(full)", foreground="#888888")
```

- [ ] **Step 4: Reset trim when a new audio file is chosen**

In `_browse_audio`, inside `if path:`, after the output-suggestion block, add:

```python
            self.trim_enabled.set(False)
            self.trim_start.set(0.0)
            self.trim_end.set(0.0)
            self._audio_duration = 0.0
```

- [ ] **Step 5: Thread trim params into the worker**

In `_worker`, compute the trim values once near the top of the `try` block (after the inner `status` / `video_progress` defs, before `segments = transcribe(...)`):

```python
            trim_start = self.trim_start.get() if self.trim_enabled.get() else None
            trim_end = self.trim_end.get() if self.trim_enabled.get() else None
```

Change the `transcribe(...)` call to:

```python
            segments = transcribe(
                audio_path, model_size=self.model_size.get(),
                status_callback=status, trim_start=trim_start, trim_end=trim_end,
            )
```

Add the two args to the `compose_video(...)` call (after `progress_callback=video_progress,`):

```python
                trim_start=trim_start,
                trim_end=trim_end,
```

- [ ] **Step 6: Persist trim in collect/apply**

In `_collect_settings`, add to the returned dict (after the `wf_*` entries):

```python
            "trim_enabled": self.trim_enabled.get(),
            "trim_start": self.trim_start.get(),
            "trim_end": self.trim_end.get(),
```

In `_apply_settings`, add (after the `wf_*` block):

```python
        self.trim_enabled.set(data.get("trim_enabled", False))
        self.trim_start.set(data.get("trim_start", 0.0))
        self.trim_end.set(data.get("trim_end", 0.0))
```

- [ ] **Step 7: Manual verification**

The dialog itself lands in Task 7, so verify the integration points here:

Run: `python main.py`
Confirm:
1. App launches; a **Trim Audio…** button with a grey `(full)` status appears under Input Files.
2. Clicking **Trim Audio…** raises `ModuleNotFoundError` for `gui.trim_dialog` (expected until Task 7) — the button is wired.
3. In a Python shell: `python -c "import gui.app"` imports cleanly (no syntax errors).

- [ ] **Step 8: Commit**

```bash
git add gui/app.py
git commit -m "Wire trim state, launcher, and worker params into the app"
```

---

### Task 7: Trim dialog (gui/trim_dialog.py)

**Files:**
- Create: `gui/trim_dialog.py`

**Interfaces:**
- Consumes: app vars/methods from Task 6 (`trim_enabled`, `trim_start`, `trim_end`, `_audio_duration`, `_overview_cache`, `audio_path`); `core.trim.clamp_range`, `format_timecode`, `parse_timecode` (Task 1); `core.waveform.load_audio_overview` (Task 2).
- Produces: `TrimDialog(parent, app)`.

GUI code — verification is the manual checklist in Step 3. All math goes through helpers unit-tested in Tasks 1-2.

- [ ] **Step 1: Create `gui/trim_dialog.py`**

```python
import threading
import tkinter as tk
from tkinter import ttk

from core.trim import clamp_range, format_timecode, parse_timecode

_OVERVIEW_W = 560
_OVERVIEW_H = 90
_DETAIL_W = 270
_DETAIL_H = 70
_DETAIL_WINDOW = 3.0   # seconds shown on each side of a handle in detail strips
_BUCKETS = 560


class TrimDialog(tk.Toplevel):
    """Modal in/out trim selector editing the app's shared trim vars in place."""

    def __init__(self, parent: tk.Tk, app) -> None:
        super().__init__(parent)
        self.app = app
        self.title("Trim Audio")
        self.resizable(False, False)
        self.transient(parent)
        self.update_idletasks()
        self.grab_set()

        self._envelope = None          # np.ndarray 0..1 or None until analyzed
        self._duration = 0.0
        self._drag_handle = None       # "start" | "end" | None

        self._build_ui()
        self._traces = [
            self.app.trim_start.trace_add("write", self._on_vars_changed),
            self.app.trim_end.trace_add("write", self._on_vars_changed),
        ]
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._load_overview()

    # ---- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        self._status = ttk.Label(frm, text="Analyzing audio…")
        self._status.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 6))

        self._overview = tk.Canvas(frm, width=_OVERVIEW_W, height=_OVERVIEW_H,
                                   bg="#1e1e1e", highlightthickness=0)
        self._overview.grid(row=1, column=0, columnspan=4, pady=(0, 8))
        self._overview.bind("<Button-1>", self._on_overview_press)
        self._overview.bind("<B1-Motion>", self._on_overview_drag)
        self._overview.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag_handle", None))

        # Detail strips
        ttk.Label(frm, text="In point").grid(row=2, column=0, sticky=tk.W)
        ttk.Label(frm, text="Out point").grid(row=2, column=2, sticky=tk.W)
        self._detail_in = tk.Canvas(frm, width=_DETAIL_W, height=_DETAIL_H,
                                    bg="#1e1e1e", highlightthickness=0)
        self._detail_in.grid(row=3, column=0, columnspan=2, padx=(0, 8), pady=(0, 8))
        self._detail_out = tk.Canvas(frm, width=_DETAIL_W, height=_DETAIL_H,
                                     bg="#1e1e1e", highlightthickness=0)
        self._detail_out.grid(row=3, column=2, columnspan=2, pady=(0, 8))
        self._detail_in.bind("<B1-Motion>", lambda e: self._on_detail_drag("start", e))
        self._detail_out.bind("<B1-Motion>", lambda e: self._on_detail_drag("end", e))

        # Numeric fields + nudges
        self._in_var = tk.StringVar()
        self._out_var = tk.StringVar()
        self._build_numeric_row(frm, 4, "In:", self._in_var, "start")
        self._build_numeric_row(frm, 5, "Out:", self._out_var, "end")

        self._readout = ttk.Label(frm, text="")
        self._readout.grid(row=6, column=0, columnspan=4, sticky=tk.W, pady=(4, 6))

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=4, sticky=tk.EW)
        ttk.Button(btns, text="Use Full Audio", command=self._use_full).pack(side=tk.LEFT)
        ttk.Button(btns, text="Close", command=self._close).pack(side=tk.RIGHT)

    def _build_numeric_row(self, frm, row, label, var, which) -> None:
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        entry = ttk.Entry(frm, textvariable=var, width=10)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind("<Return>", lambda e: self._commit_numeric(var, which))
        entry.bind("<FocusOut>", lambda e: self._commit_numeric(var, which))
        nudge = ttk.Frame(frm)
        nudge.grid(row=row, column=2, columnspan=2, sticky=tk.W)
        for label_text, delta in [("-1s", -1.0), ("-0.1s", -0.1), ("+0.1s", 0.1), ("+1s", 1.0)]:
            ttk.Button(nudge, text=label_text, width=5,
                       command=lambda d=delta, w=which: self._nudge(w, d)).pack(side=tk.LEFT, padx=1)

    # ---- overview analysis (background thread) ---------------------------

    def _load_overview(self) -> None:
        path = self.app.audio_path.get().strip()
        if not path:
            self._status.config(text="No audio file selected.")
            return
        cached = self.app._overview_cache.get(path)
        if cached is not None:
            self._on_overview_ready(*cached)
            return

        def work():
            from core.waveform import load_audio_overview
            try:
                env, dur = load_audio_overview(path, _BUCKETS)
            except Exception as exc:  # pragma: no cover - I/O failure path
                self.after(0, lambda: self._status.config(text=f"Could not read audio: {exc}"))
                return
            self.app._overview_cache[path] = (env, dur)
            self.after(0, lambda: self._on_overview_ready(env, dur))

        threading.Thread(target=work, daemon=True).start()

    def _on_overview_ready(self, env, dur) -> None:
        self._envelope = env
        self._duration = dur
        self.app._audio_duration = dur
        if not self.app.trim_enabled.get() or self.app.trim_end.get() <= 0:
            self.app.trim_start.set(0.0)
            self.app.trim_end.set(dur)
        self._status.config(text=f"Drag the handles or type exact times. Duration {format_timecode(dur)}.")
        self._sync_from_vars()

    # ---- selection editing ----------------------------------------------

    def _set_range(self, start, end) -> None:
        start, end = clamp_range(start, end, self._duration)
        self.app.trim_enabled.set(True)
        self.app.trim_start.set(start)
        self.app.trim_end.set(end)

    def _commit_numeric(self, var, which) -> None:
        val = parse_timecode(var.get())
        if val is None:
            self._sync_from_vars()
            return
        if which == "start":
            self._set_range(val, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), val)

    def _nudge(self, which, delta) -> None:
        if which == "start":
            self._set_range(self.app.trim_start.get() + delta, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), self.app.trim_end.get() + delta)

    def _use_full(self) -> None:
        self.app.trim_enabled.set(False)
        self.app.trim_start.set(0.0)
        self.app.trim_end.set(self._duration)
        self._sync_from_vars()

    def _x_to_time(self, x) -> float:
        if self._duration <= 0:
            return 0.0
        return max(0.0, min(self._duration, (x / _OVERVIEW_W) * self._duration))

    def _on_overview_press(self, event) -> None:
        t = self._x_to_time(event.x)
        mid = (self.app.trim_start.get() + self.app.trim_end.get()) / 2
        self._drag_handle = "start" if t < mid else "end"
        self._on_overview_drag(event)

    def _on_overview_drag(self, event) -> None:
        if self._drag_handle is None:
            return
        t = self._x_to_time(event.x)
        if self._drag_handle == "start":
            self._set_range(t, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), t)

    def _on_detail_drag(self, which, event) -> None:
        anchor = self.app.trim_start.get() if which == "start" else self.app.trim_end.get()
        lo = anchor - _DETAIL_WINDOW
        frac = max(0.0, min(1.0, event.x / _DETAIL_W))
        t = lo + frac * (2 * _DETAIL_WINDOW)
        if which == "start":
            self._set_range(t, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), t)

    # ---- rendering -------------------------------------------------------

    def _on_vars_changed(self, *_) -> None:
        self._sync_from_vars()

    def _sync_from_vars(self) -> None:
        s = self.app.trim_start.get()
        e = self.app.trim_end.get()
        self._in_var.set(format_timecode(s))
        self._out_var.set(format_timecode(e))
        self._readout.config(
            text=f"Selection: {format_timecode(e - s)}  (of {format_timecode(self._duration)})"
        )
        self._draw_overview()
        self._draw_detail(self._detail_in, s)
        self._draw_detail(self._detail_out, e)

    def _draw_envelope(self, canvas, env_slice, w, h) -> None:
        n = len(env_slice)
        if n == 0:
            return
        mid = h / 2
        step = w / n
        for i, lv in enumerate(env_slice):
            x = i * step
            half = (h / 2) * float(lv)
            canvas.create_line(x, mid - half, x, mid + half, fill="#4a90d9")

    def _draw_overview(self) -> None:
        c = self._overview
        c.delete("all")
        if self._envelope is None:
            return
        self._draw_envelope(c, self._envelope, _OVERVIEW_W, _OVERVIEW_H)
        if self._duration <= 0:
            return
        x0 = (self.app.trim_start.get() / self._duration) * _OVERVIEW_W
        x1 = (self.app.trim_end.get() / self._duration) * _OVERVIEW_W
        c.create_rectangle(0, 0, x0, _OVERVIEW_H, fill="#000000", stipple="gray50", outline="")
        c.create_rectangle(x1, 0, _OVERVIEW_W, _OVERVIEW_H, fill="#000000", stipple="gray50", outline="")
        for x in (x0, x1):
            c.create_line(x, 0, x, _OVERVIEW_H, fill="#ffdc00", width=2)

    def _draw_detail(self, canvas, center_t) -> None:
        canvas.delete("all")
        if self._envelope is None or self._duration <= 0:
            return
        lo = center_t - _DETAIL_WINDOW
        hi = center_t + _DETAIL_WINDOW
        n = len(self._envelope)
        i0 = max(0, int((lo / self._duration) * n))
        i1 = min(n, int((hi / self._duration) * n))
        if i1 > i0:
            self._draw_envelope(canvas, self._envelope[i0:i1], _DETAIL_W, _DETAIL_H)
        canvas.create_line(_DETAIL_W / 2, 0, _DETAIL_W / 2, _DETAIL_H, fill="#ffdc00", width=2)

    # ---- teardown --------------------------------------------------------

    def _close(self) -> None:
        self.app.trim_start.trace_remove("write", self._traces[0])
        self.app.trim_end.trace_remove("write", self._traces[1])
        self.grab_release()
        self.destroy()
```

- [ ] **Step 2: Verify it imports**

Run: `python -c "import gui.trim_dialog"`
Expected: no output, exit 0.

- [ ] **Step 3: Manual verification**

Run: `python main.py`, pick a long audio file, click **Trim Audio…**. Confirm:
1. "Analyzing audio…" shows briefly, then the overview waveform renders with two yellow handles and the selection spanning the full file.
2. Dragging a handle on the overview moves it; the dimmed regions and the In/Out fields update live; handles can't cross and stop at a ≥0.5s gap.
3. The In/Out detail strips show a zoomed view centered on each handle; dragging inside a detail strip fine-moves that handle.
4. Typing `0:30` into **In** and pressing Enter moves the in-point to 30s; the nudge buttons shift by ±0.1s / ±1s.
5. The status label in the main window turns green and shows the range; **Use Full Audio** resets it to grey `(full)`.
6. Reopening the dialog for the same file is instant (cached); the prior selection is preserved.

- [ ] **Step 4: Commit**

```bash
git add gui/trim_dialog.py
git commit -m "Add Trim Audio dialog with overview + detail scrubber"
```

---

### Task 8: Document the trim feature in README.md

**Files:**
- Modify: `README.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Add a Features bullet**

In the `## Features` list, add a bullet (after the background-support line):

```markdown
- Audio trimming — pick an in/out highlight window in a waveform scrubber; only that window is transcribed and rendered
```

- [ ] **Step 2: Document the Trim dialog**

Add a subsection describing the dialog. Place it near the other settings documentation (after the waveform/settings section, or under "Usage" if the simpler README is present):

```markdown
### Trim Audio

Open the **Trim Audio…** dialog to select a highlight window instead of rendering the whole file. The status next to the button shows `(full)` or the chosen range.

| Control | Meaning |
|---|---|
| **Overview waveform** | The full file. Drag the two handles to set the coarse in/out points; the area outside the selection is dimmed. |
| **In / Out detail strips** | A zoomed view around each handle (±3s) for fine placement — drag inside a strip to nudge that handle precisely. |
| **In / Out fields** | Exact `m:ss.s` entry, each with ±0.1s / ±1s nudge buttons. Handles, detail strips, and fields stay in sync. |
| **Use Full Audio** | Clears the trim and renders the entire file. |

Trimming happens **before** transcription, so picking a 60-second window means Whisper only processes those 60 seconds — dramatically faster than transcribing a full episode. The selection resets when you choose a different audio file.
```

- [ ] **Step 3: Verify and commit**

Run: `git diff --stat`
Expected: `README.md` modified.

```bash
git add README.md
git commit -m "Document audio trim feature in README"
```

---

## Notes for the executor

- Run the full suite after each task: `python -m pytest -v` from the repo root.
- Tasks 6 and 7 are tkinter GUI code with no automated tests (matching the existing codebase); their correctness rests on the unit-tested helpers plus the manual checklists. Report the manual checklist results in the task report.
- The final whole-branch review should confirm: trim-before-transcription wiring (Tasks 3 + 6), subclip alignment (Task 4 + 6), and that segment timestamps stay clip-relative end-to-end.
