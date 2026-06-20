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
