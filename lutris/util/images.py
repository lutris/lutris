"""Image files: finding Lutris's own images, and processing images with Pillow

Nothing here draws anything; frontends load the files these return, or that
these write, with their own toolkit.
"""

import os

from PIL import Image

from lutris import settings
from lutris.util import datapath, magic


def get_image_file_extension(path: str) -> str | None:
    """Returns the canonical file extension for an image,
    either 'jpg' or 'png'; we deduce this from the file extension, or if that fails the
    file's 'magic' prefix bytes."""
    ext = os.path.splitext(path)[1].casefold()
    if ext in [".jpg", ".jpeg"]:
        return ".jpg"
    if ext == ".png":
        return ".png"

    try:
        file_type = magic.from_file(path).casefold()
    except OSError:
        return None  # file is missing, or can't read it

    if "jpeg image data" in file_type:
        return ".jpg"
    if "png image data" in file_type:
        return ".png"

    return None


def get_default_icon_path(size: tuple[int, int]) -> str:
    """Returns the path to the default icon for the size given; it's
    a Lutris icon for a square size, and a gradient for other sizes."""
    if size[0] == size[1]:
        filename = "media/default_icon.png"
    else:
        filename = "media/default_banner.png"
    return os.path.join(datapath.get(), filename)


def get_runtime_icon_path(icon_name: str) -> str | None:
    """Finds the icon file for an icon whose name is given; this searches the icons
    in Lutris's runtime directory. The name is normalized by removing spaces
    and lower-casing it, and both .png and .svg files with the name can be found.

    Arguments:
    icon_name -- The name of the icon to retrieve

    Returns:
        The path to the icon, or None if it wasn't found.
    """
    filename = icon_name.lower().replace(" ", "")
    # We prefer bitmaps over SVG, because we've got some SVG icons with the
    # wrong size (oops) and this avoids them.
    search_directories = [
        "icons/hicolor/64x64/apps",
        "icons/hicolor/24x24/apps",
        "icons",
        "icons/hicolor/scalable/apps",
        "icons/hicolor/symbolic/apps",
    ]
    extensions = [".png", ".svg"]
    for search_dir in search_directories:
        for ext in extensions:
            icon_path = os.path.join(settings.RUNTIME_DIR, search_dir, filename + ext)
            if os.path.exists(icon_path):
                return icon_path
    return None


def thumbnail_image(base_image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Scales an image to cover the target size, and crops what overflows it equally on both sides."""
    base_width, base_height = base_image.size
    base_ratio = base_width / base_height
    target_width, target_height = target_size
    target_ratio = target_width / target_height

    # Resize and crop coverart
    if base_ratio >= target_ratio:
        width = int(base_width * (target_height / base_height))
        height = target_height
    else:
        width = target_width
        height = int(base_height * (target_width / base_width))
    x_offset = int((width - target_width) / 2)
    y_offset = int((height - target_height) / 2)
    base_image = base_image.resize((width, height), resample=Image.Resampling.BICUBIC)
    base_image = base_image.crop((x_offset, y_offset, width - x_offset, height - y_offset))
    return base_image


def paste_overlay(base_image: Image.Image, overlay_image: Image.Image) -> Image.Image:
    """Pastes an image, through its own transparency, in the middle of another."""
    base_width, base_height = base_image.size
    overlay_width, overlay_height = overlay_image.size
    offset_x = int((base_width - overlay_width) / 2)
    offset_y = int((base_height - overlay_height) / 2)
    base_image.paste(
        overlay_image, (offset_x, offset_y, overlay_width + offset_x, overlay_height + offset_y), mask=overlay_image
    )
    return base_image
