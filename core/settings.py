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
    "font_weight": "Font Default",
    # Caption colors
    "text_color": "#FFFFFF",
    "highlight_color": "#FFDC00",
    "highlight_enabled": True,
    "caption_position": "Bottom",
    "caption_bg_opacity": 73.0,
    "caption_bg_edge_style": "Hard",
    "caption_bg_edge_size": 40,
    # Caption transitions
    "text_in": "None",
    "text_out": "None",
    "text_transition_duration": 0.3,
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


# ----------------------------------------------------------------------
# Configuration export / import / named presets
# ----------------------------------------------------------------------

_PRESETS_DIR = _SETTINGS_DIR / "presets"
_FORMAT_KEY = "audiogrammer_config"
_FORMAT_VERSION = 1


def sanitize(data: dict) -> dict:
    """Return a full settings dict built from untrusted ``data``.

    Unknown keys are dropped; missing keys or values whose type does not match
    the default fall back to the default.
    """
    clean = {}
    for key, default in DEFAULTS.items():
        value = data.get(key, default) if isinstance(data, dict) else default
        if isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, (int, float)):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            if ok and isinstance(default, float):
                value = float(value)
        elif isinstance(default, list):
            ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
        else:
            ok = isinstance(value, str)
        clean[key] = value if ok else default
    return clean


def export_config(data: dict, path) -> None:
    payload = {_FORMAT_KEY: _FORMAT_VERSION, "settings": sanitize(data)}
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def import_config(path) -> dict:
    """Read a config file written by :func:`export_config`.

    Raises ``ValueError`` if the file is not valid JSON or not a config.
    """
    try:
        with Path(path).open(encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Could not read configuration file: {e}") from e
    if isinstance(payload, dict) and _FORMAT_KEY in payload:
        payload = payload.get("settings")
    if not isinstance(payload, dict) or not any(k in payload for k in DEFAULTS):
        raise ValueError("File does not contain Audiogrammer settings.")
    return sanitize(payload)


def _preset_path(name: str) -> Path:
    safe = "".join(c for c in name.strip() if c.isalnum() or c in " -_.()").strip(" .")
    if not safe:
        raise ValueError("Preset name must contain letters or numbers.")
    return _PRESETS_DIR / f"{safe}.json"


def list_presets() -> list:
    if not _PRESETS_DIR.is_dir():
        return []
    return sorted((p.stem for p in _PRESETS_DIR.glob("*.json")), key=str.lower)


def save_preset(name: str, data: dict) -> None:
    path = _preset_path(name)
    _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    export_config(data, path)


def load_preset(name: str) -> dict:
    return import_config(_preset_path(name))


def delete_preset(name: str) -> None:
    try:
        _preset_path(name).unlink()
    except FileNotFoundError:
        pass
