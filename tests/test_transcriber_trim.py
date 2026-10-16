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


def test_transcribe_trims_with_ffmpeg_before_whisper(monkeypatch):
    captured = {}
    _install_fake_whisper(monkeypatch, captured)
    import core.audio_trim as audio_trim
    from core.transcriber import transcribe

    calls = []

    def fake_trim(path, start, end, sr=16000):
        calls.append((path, start, end, sr))
        return np.zeros(int((end - start) * sr), dtype=np.float32)

    monkeypatch.setattr(audio_trim, "trim_audio_ffmpeg", fake_trim)

    transcribe("episode.mp3", model_size="base", trim_start=2.0, trim_end=5.0)

    assert calls == [("episode.mp3", 2.0, 5.0, 16000)]
    # Whisper receives only the 3s trimmed window, not the full 10s file
    assert len(captured["audio"]) == 3 * 16000


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
