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
