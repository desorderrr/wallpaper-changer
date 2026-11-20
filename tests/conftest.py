import pytest


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Isola os dados da app numa pasta temporária."""
    monkeypatch.setenv("WPC_DATA_DIR", str(tmp_path))
    from wallpaper_changer import config, history

    history.reset()
    config.load_settings()
    config.ensure_dirs()
    yield tmp_path
    history.reset()
