import pytest


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Isola os dados da app numa pasta temporária."""
    monkeypatch.setenv("WPC_DATA_DIR", str(tmp_path))
    from wallpaper_changer import config

    config.load_settings()
    config.ensure_dirs()
    yield tmp_path
