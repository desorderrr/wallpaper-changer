import io

from PIL import Image

from wallpaper_changer import history


def jpg(color, size=(64, 64), quality=90):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "JPEG", quality=quality)
    return b.getvalue()


def test_add_and_detect(data_dir):
    data = jpg((10, 10, 10))
    assert not history.is_duplicate(data)
    history.add(data, "teste")
    assert history.is_duplicate(data)
    assert history.count() == 1


def test_recompressed_image_is_detected(data_dir):
    base = Image.open(io.BytesIO(jpg((120, 60, 30), (640, 360), 95)))
    a = io.BytesIO()
    base.save(a, "JPEG", quality=95)
    history.add(a.getvalue(), "teste")

    # same image, smaller and with different compression
    b = io.BytesIO()
    base.resize((320, 180)).save(b, "JPEG", quality=60)
    assert history.is_duplicate(b.getvalue())


def test_different_images_not_detected(data_dir):
    history.add(jpg((0, 0, 0)), "teste")
    assert not history.is_duplicate(jpg((255, 255, 255)))


def test_reset_forgets_history(data_dir):
    data = jpg((10, 10, 10))
    history.add(data, "teste")
    history.reset()
    assert not history.is_duplicate(data)
    assert history.count() == 0


def test_history_is_persisted(data_dir):
    data = jpg((30, 30, 30))
    history.add(data, "teste", "x.jpg")
    # clear the in-memory cache and reload from disk
    history._items = None
    assert history.is_duplicate(data)


def test_seed_from_folder(data_dir):
    from wallpaper_changer import config

    img = jpg((70, 70, 70))
    (config.image_dir() / "bing_20260101_000000_000001.jpg").write_bytes(img)
    assert history.count() == 0

    assert history.seed_from_folder() == 1
    assert history.is_duplicate(img)
    # if history already exists, do not seed again
    assert history.seed_from_folder() == 0


def test_pick_for_tone_returns_matching_saved_image(data_dir):
    from wallpaper_changer import config

    dark = jpg((10, 10, 10))
    light = jpg((250, 250, 250))
    dark_path = config.image_dir() / "bing_dark.jpg"
    light_path = config.image_dir() / "bing_light.jpg"
    dark_path.write_bytes(dark)
    light_path.write_bytes(light)
    history.add(dark, "bing", dark_path)
    history.add(light, "bing", light_path)

    assert history.pick_for_tone(True) == dark_path
    assert history.pick_for_tone(False) == light_path


def test_pick_for_tone_respects_exclude_and_missing_files(data_dir):
    from wallpaper_changer import config

    dark = jpg((10, 10, 10))
    path = config.image_dir() / "bing_x.jpg"
    path.write_bytes(dark)
    history.add(dark, "bing", path)

    assert history.pick_for_tone(True, exclude=str(path)) is None
    path.unlink()
    assert history.pick_for_tone(True) is None
