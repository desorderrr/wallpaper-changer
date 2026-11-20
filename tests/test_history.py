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

    # mesma imagem, menor e com compressão diferente
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
    # limpa a cache em memória e recarrega do ficheiro
    history._items = None
    assert history.is_duplicate(data)


def test_seed_from_folder(data_dir):
    from wallpaper_changer import config

    img = jpg((70, 70, 70))
    (config.image_dir() / "bing_20260101_000000_000001.jpg").write_bytes(img)
    assert history.count() == 0

    assert history.seed_from_folder() == 1
    assert history.is_duplicate(img)
    # se já houver histórico, não semeia outra vez
    assert history.seed_from_folder() == 0
