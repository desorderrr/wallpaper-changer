import json

from wallpaper_changer import config


def test_defaults(data_dir):
    assert config.get("interval") == "daily"
    assert config.get("theme_mode") == "auto"
    assert isinstance(config.get("queries_dark"), list)


def test_roundtrip(data_dir):
    config.set_key("interval", "3h")
    config.set_key("keep", 9)
    config.load_settings()
    assert config.get("interval") == "3h"
    assert config.get("keep") == 9
    data = json.loads(config.settings_file().read_text(encoding="utf-8"))
    assert data["interval"] == "3h"


def test_corrupted_json_is_ignored(data_dir):
    config.settings_file().write_text("{isto nao e json", encoding="utf-8")
    config.load_settings()
    assert config.get("interval") == "daily"


def test_non_dict_json_is_ignored(data_dir):
    config.settings_file().write_text("[1, 2, 3]", encoding="utf-8")
    config.load_settings()
    assert config.get("theme_mode") == "auto"


def test_unknown_keys_ignored(data_dir):
    config.settings_file().write_text(
        json.dumps({"interval": "1h", "chave_estranha": True}), encoding="utf-8"
    )
    config.load_settings()
    assert config.get("interval") == "1h"
    assert config.get("chave_estranha") is None


def test_interval_label_migration(data_dir):
    config.settings_file().write_text(
        json.dumps({"interval": "Apenas ao iniciar", "theme_mode": "x"}),
        encoding="utf-8",
    )
    config.load_settings()
    assert config.get("interval") == "startup_only"
    assert config.get("theme_mode") == "auto"


def test_keep_validation(data_dir):
    config.settings_file().write_text(
        json.dumps({"keep": 9999}), encoding="utf-8"
    )
    config.load_settings()
    assert config.get("keep") == 200


def test_new_defaults_and_intervals(data_dir):
    assert config.get("use_wallhaven") is False
    assert config.get("paused") is False
    assert "5m" in config.INTERVALS
    assert "12h" in config.INTERVALS
    assert len(config.INTERVAL_LABELS) == len(config.INTERVALS) + 1  # + startup_only


def test_set_many_writes_once(data_dir, monkeypatch):
    writes = []
    monkeypatch.setattr(config, "save_settings", lambda: writes.append(1))
    config.set_many({"interval": "3h", "keep": 9, "theme_mode": "dark"})
    assert writes == [1]
    assert config.get("interval") == "3h"
    assert config.get("keep") == 9
    assert config.get("theme_mode") == "dark"


def test_empty_queries_fall_back_to_defaults(data_dir):
    config.set_key("queries_dark", [])
    assert config.get("queries_dark") == config.DEFAULTS["queries_dark"]
    config.set_key("queries_light", "não é uma lista")
    assert config.get("queries_light") == config.DEFAULTS["queries_light"]
    config.load_settings()
    assert config.get("queries_dark") == config.DEFAULTS["queries_dark"]
    assert config.get("queries_light") == config.DEFAULTS["queries_light"]
