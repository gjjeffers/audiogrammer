import core.settings as settings


def test_defaults_include_trim_keys():
    assert settings.DEFAULTS["trim_enabled"] is False
    assert settings.DEFAULTS["trim_start"] == 0.0
    assert settings.DEFAULTS["trim_end"] == 0.0


def test_load_fills_trim_defaults(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "_SETTINGS_FILE", f)
    loaded = settings.load()
    assert loaded["trim_enabled"] is False
    assert loaded["trim_start"] == 0.0
    assert loaded["trim_end"] == 0.0


def test_save_then_load_roundtrips_trim(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "_SETTINGS_FILE", f)
    data = dict(settings.DEFAULTS)
    data.update(trim_enabled=True, trim_start=12.5, trim_end=72.0)
    settings.save(data)
    loaded = settings.load()
    assert loaded["trim_enabled"] is True
    assert loaded["trim_start"] == 12.5
    assert loaded["trim_end"] == 72.0
