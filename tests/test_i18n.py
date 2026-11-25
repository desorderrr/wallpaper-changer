# -*- coding: utf-8 -*-
"""Testes do sistema de traduções."""

from __future__ import annotations

import ast
import types
from pathlib import Path

import pytest

from wallpaper_changer import config, i18n


@pytest.fixture(autouse=True)
def restore_language():
    """Nenhum teste pode deixar a app noutro idioma."""
    previous = i18n.current_language()
    yield
    i18n.set_language(previous)


def test_portuguese_is_the_source():
    i18n.set_language("pt")
    assert i18n.t("Gravar") == "Gravar"
    assert i18n.t("Tema atual: %s (%s)") == "Tema atual: %s (%s)"


def test_english_translation():
    i18n.set_language("en")
    assert i18n.t("Gravar") == "Save"
    assert i18n.t("Mudar agora") == "Change now"
    assert i18n.t("escuro") == "dark"
    full = i18n.t("Tema atual: %s (%s)") % ("dark", "follows the system")
    assert full == "Current theme: dark (follows the system)"


def test_unknown_key_falls_back_to_source():
    i18n.set_language("en")
    assert i18n.t("chave inexistente") == "chave inexistente"


def test_unknown_language_does_not_change_anything():
    i18n.set_language("en")
    i18n.set_language("xx")
    assert i18n.current_language() == "en"


def test_detect_from_environment(monkeypatch):
    # força o ramo POSIX mesmo a correr em Windows
    monkeypatch.setattr(i18n, "sys", types.SimpleNamespace(platform="linux"))
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        monkeypatch.setenv(var, "")

    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    assert i18n.detect_system_language() == "pt"
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert i18n.detect_system_language() == "en"
    monkeypatch.setenv("LANG", "")
    assert i18n.detect_system_language() == "en"


def test_apply_language_follows_settings(data_dir, monkeypatch):
    monkeypatch.setattr(i18n, "sys", types.SimpleNamespace(platform="linux"))
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("LANG", "pt_PT.UTF-8")

    config.set_key("language", "auto")
    i18n.apply_language()
    assert i18n.current_language() == "pt"

    config.set_key("language", "en")
    i18n.apply_language()
    assert i18n.current_language() == "en"


def test_invalid_language_setting_is_normalised(data_dir):
    config.settings_file().write_text('{"language": "klingon"}', encoding="utf-8")
    config.load_settings()
    assert config.get("language") == "auto"


def test_interval_labels_are_translated(data_dir):
    i18n.set_language("en")
    labels = config.interval_labels()
    assert labels[0] == ("startup_only", "Only at startup")
    assert len(labels) == len(config.INTERVAL_LABELS)


def test_every_translatable_string_has_an_english_version():
    """Nenhuma chamada t("...") pode ficar sem entrada no catálogo inglês."""
    root = Path(__file__).resolve().parents[1] / "src"
    keys: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.append(node.args[0].value)
    assert keys, "nenhuma string traduzível encontrada"
    missing = sorted(set(keys) - set(i18n.CATALOGS["en"]))
    assert not missing, "traduções em falta: %r" % missing
