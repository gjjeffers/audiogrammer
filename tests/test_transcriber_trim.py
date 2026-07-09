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


def test_transcribe_no_trim_passes_full_audio(monkeypatch):
    captured = {}
    _install_fake_whisper(monkeypatch, captured)
    from core.transcriber import transcribe

    transcribe("episode.mp3", model_size="base")

    # No trim window -> the full 10s array is passed through, not the raw path
    # (audio is always loaded as an array so duration can be derived for
    # hallucination clipping; see core.transcriber.transcribe).
    assert len(captured["audio"]) == 10 * 16000
    assert captured["audio"][0] == 0
