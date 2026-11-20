"""Tests for lutris.util.images: image processing that needs no UI toolkit."""

import os

from PIL import Image

from lutris.util.images import get_default_icon_path, get_image_file_extension, paste_overlay, thumbnail_image


def test_thumbnail_covers_the_target_and_crops_the_overflow():
    wide = Image.new("RGB", (400, 100), "red")
    thumbnail = thumbnail_image(wide, (100, 100))
    assert thumbnail.size == (100, 100)

    tall = Image.new("RGB", (100, 400), "red")
    assert thumbnail_image(tall, (200, 100)).size == (200, 100)


def test_overlay_is_pasted_in_the_middle_through_its_transparency():
    base = Image.new("RGBA", (30, 30), (0, 0, 0, 255))
    overlay = Image.new("RGBA", (10, 10), (255, 255, 255, 255))
    overlay.putpixel((0, 0), (255, 255, 255, 0))

    result = paste_overlay(base, overlay)

    assert result.getpixel((15, 15)) == (255, 255, 255, 255)
    assert result.getpixel((10, 10)) == (0, 0, 0, 255)  # The overlay's transparent corner
    assert result.getpixel((5, 5)) == (0, 0, 0, 255)


def test_image_extension_comes_from_the_name_or_the_contents(tmp_path):
    assert get_image_file_extension("cover.jpeg") == ".jpg"
    assert get_image_file_extension("icon.PNG") == ".png"

    unnamed = tmp_path / "download"
    Image.new("RGB", (4, 4)).save(unnamed, format="PNG")
    assert get_image_file_extension(str(unnamed)) == ".png"
    assert get_image_file_extension(str(tmp_path / "missing")) is None


def test_default_icon_depends_on_the_shape():
    assert os.path.basename(get_default_icon_path((32, 32))) == "default_icon.png"
    assert os.path.basename(get_default_icon_path((184, 69))) == "default_banner.png"
