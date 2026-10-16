import wave

import numpy as np
import pytest

from core.audio_trim import trim_audio_ffmpeg


def _write_wav(path, seconds=4, sr=8000):
    t = np.arange(seconds * sr)
    # Value encodes the second so the window can be verified: 0.1 * (second + 1)
    data = (0.1 * (t // sr + 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def test_trim_audio_ffmpeg_extracts_window_at_whisper_format(tmp_path):
    src = tmp_path / "in.wav"
    _write_wav(src)

    out = trim_audio_ffmpeg(str(src), 1.0, 3.0)

    assert out.dtype == np.float32
    assert len(out) == pytest.approx(2 * 16000, abs=200)
    # Window covers seconds 2 and 3 (values 0.2 and 0.3), not 1 or 4
    assert out[:100].mean() == pytest.approx(0.2, abs=0.02)
    assert out[-100:].mean() == pytest.approx(0.3, abs=0.02)


def test_trim_audio_ffmpeg_raises_on_bad_input(tmp_path):
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        trim_audio_ffmpeg(str(tmp_path / "missing.wav"), 0.0, 1.0)
