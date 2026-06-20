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
