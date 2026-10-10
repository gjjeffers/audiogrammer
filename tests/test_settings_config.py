import json

import pytest

import core.settings as settings


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "_PRESETS_DIR", tmp_path / "presets")


def test_export_import_roundtrip(tmp_path):
    data = dict(settings.DEFAULTS, font_size=99, text_color="#123456", wf_enabled=True)
    p = tmp_path / "cfg.json"
    settings.export_config(data, p)
    assert settings.import_config(p) == data


def test_import_drops_unknown_and_bad_types(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"font_size": "huge", "fps": 30, "bogus": 1,
                             "wf_enabled": 1, "wm_opacity": 50}))
    cfg = settings.import_config(p)
    assert cfg["font_size"] == settings.DEFAULTS["font_size"]
    assert cfg["fps"] == 30
    assert cfg["wf_enabled"] is False
    assert cfg["wm_opacity"] == 50.0
    assert "bogus" not in cfg


@pytest.mark.parametrize("content", ["not json", "[1, 2]", '{"hello": 1}'])
def test_import_rejects_invalid(tmp_path, content):
    p = tmp_path / "cfg.json"
    p.write_text(content)
    with pytest.raises(ValueError):
        settings.import_config(p)


def test_import_missing_file(tmp_path):
    with pytest.raises(ValueError):
        settings.import_config(tmp_path / "nope.json")


def test_presets_save_list_load_delete():
    assert settings.list_presets() == []
    data = dict(settings.DEFAULTS, fps=60)
    settings.save_preset("My Preset", data)
    settings.save_preset("another", data)
    assert settings.list_presets() == ["another", "My Preset"]
    assert settings.load_preset("My Preset")["fps"] == 60
    settings.delete_preset("My Preset")
    assert settings.list_presets() == ["another"]


def test_preset_name_cannot_escape_dir():
    settings.save_preset("../../evil", settings.DEFAULTS)
    assert settings.list_presets() == ["evil"]
    with pytest.raises(ValueError):
        settings.save_preset("///", settings.DEFAULTS)
