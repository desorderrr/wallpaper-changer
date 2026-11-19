import io

from PIL import Image

from wallpaper_changer import tone


def img_bytes(color):
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


def test_luminance_dark_and_light():
    assert tone.mean_luminance(img_bytes((5, 5, 5))) <= 115
    assert tone.mean_luminance(img_bytes((250, 250, 250))) >= 140


def test_tone_matching():
    dark = tone.mean_luminance(img_bytes((10, 10, 10)))
    light = tone.mean_luminance(img_bytes((245, 245, 245)))
    assert tone.tone_matches(dark, want_dark=True)
    assert not tone.tone_matches(light, want_dark=True)
    assert tone.tone_matches(light, want_dark=False)
    assert not tone.tone_matches(dark, want_dark=False)
