import sys
import types

import numpy as np
import pytest
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
    def __init__(self, fail_write=False):
        self._fail_write = fail_write

    def with_fps(self, fps):
        return self

    def with_audio(self, audio):
        return self

    def write_videofile(self, *args, **kwargs):
        if self._fail_write:
            raise RuntimeError("encoding failed")


def _patch_pipeline(monkeypatch, fake_audio, bg_state=None, fail_write=False, fail_audio_load=False):
    fake_moviepy = types.ModuleType("moviepy")

    def _make_audio(path):
        if fail_audio_load:
            raise RuntimeError("could not open audio")
        return fake_audio

    fake_moviepy.AudioFileClip = _make_audio
    fake_moviepy.VideoClip = lambda make_frame, duration=None: _FakeClip(fail_write=fail_write)
    monkeypatch.setitem(sys.modules, "moviepy", fake_moviepy)

    frame = Image.new("RGBA", (32, 32), (0, 0, 0, 255))

    def _bg_cleanup():
        if bg_state is not None:
            bg_state["cleaned_up"] = True

    monkeypatch.setattr(
        composer, "_load_background", lambda *a, **k: ((lambda t: frame), _bg_cleanup)
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


def test_compose_video_cleans_up_audio_and_background_on_success(monkeypatch):
    fake_audio = _FakeAudio()
    bg_state = {"cleaned_up": False}
    _patch_pipeline(monkeypatch, fake_audio, bg_state)

    composer.compose_video(
        bg_path="bg.png",
        audio_path="a.mp3",
        segments=[],
        output_path="out.mp4",
    )

    assert fake_audio.closed
    assert bg_state["cleaned_up"]


def test_compose_video_cleans_up_audio_and_background_on_render_failure(monkeypatch):
    """A failure during encoding (or a cancelled render) must still release both resources."""
    fake_audio = _FakeAudio()
    bg_state = {"cleaned_up": False}
    _patch_pipeline(monkeypatch, fake_audio, bg_state, fail_write=True)

    with pytest.raises(RuntimeError):
        composer.compose_video(
            bg_path="bg.png",
            audio_path="a.mp3",
            segments=[],
            output_path="out.mp4",
        )

    assert fake_audio.closed
    assert bg_state["cleaned_up"]


def test_compose_video_cleans_up_background_when_audio_load_fails(monkeypatch):
    """The background (e.g. an mp4's ffmpeg subprocess) is acquired before the audio;
    if loading the audio then fails, the background must still be released."""
    fake_audio = _FakeAudio()
    bg_state = {"cleaned_up": False}
    _patch_pipeline(monkeypatch, fake_audio, bg_state, fail_audio_load=True)

    with pytest.raises(RuntimeError):
        composer.compose_video(
            bg_path="bg.png",
            audio_path="a.mp3",
            segments=[],
            output_path="out.mp4",
        )

    assert bg_state["cleaned_up"]
    assert not fake_audio.closed  # audio was never successfully created
