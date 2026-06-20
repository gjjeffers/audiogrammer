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
