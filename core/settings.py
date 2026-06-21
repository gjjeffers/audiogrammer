import json
from pathlib import Path

_SETTINGS_DIR = Path.home() / ".audiogrammer"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

ALL_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo"]

DEFAULTS = {
    # File paths
    "audio_path": "",
    "bg_path": "",
    "output_path": "audiogram.mp4",
    # Core video settings
    "model_size": "turbo",
    "visible_models": ALL_MODELS,
    "font_size": 72,
    "fps": 24,
    "resolution": "1080p 1920×1080 (16:9)",
    "quality": "High",
    "font_name": "",
    # Caption colors
    "text_color": "#FFFFFF",
    "highlight_color": "#FFDC00",
    # Watermark
    "wm_text": "",
    "wm_image_path": "",
    "wm_position": "Bottom Right",
    "wm_opacity": 70.0,
    "wm_font_size": 28,
    "wm_color": "#FFFFFF",
    # Waveform
    "wf_enabled": False,
    "wf_mode": "Reactive",
    "wf_style": "Rounded Bars",
    "wf_opacity": 90.0,
    "wf_placement": "Stretch",
    "wf_position": "Bottom",
    "wf_sensitivity": 1.0,
    "wf_smoothing": 0.5,
    "wf_mirror": False,
    "wf_bar_count": 48,
    "wf_thickness": 3,
    "wf_use_gradient": False,
    "wf_color": "#FFFFFF",
    "wf_gradient_color": "#00BFFF",
    # Trim
    "trim_enabled": False,
    "trim_start": 0.0,
    "trim_end": 0.0,
}


def load() -> dict:
    try:
        with _SETTINGS_FILE.open() as f:
            saved = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
    return {**DEFAULTS, **saved}


def save(data: dict) -> None:
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with _SETTINGS_FILE.open("w") as f:
        json.dump(data, f, indent=2)
