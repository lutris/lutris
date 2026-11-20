"""Downloading and processing service media happens in the core, without a UI."""

import os
from typing import cast

import pytest
from PIL import Image

from lutris.services.egs import DieselGameBoxTall
from lutris.services.service_media import MEDIA_CACHE_INVALIDATED, ServiceMedia, download_media


class FakeMedia(ServiceMedia):
    service = "test"
    size = (10, 10)
    file_patterns = ["%s.png"]

    def __init__(self, folder):
        self.dest_path = self.folder = folder
        super().__init__()

    def download(self, slug, url):
        if url == "broken":
            raise RuntimeError("download failed")
        if url == "missing":
            return None
        path = os.path.join(self.folder, self.get_filename(slug))
        Image.new("RGB", self.size).save(path)
        return path


@pytest.fixture
def invalidations(fake_main_loop):
    fired = []
    registration = MEDIA_CACHE_INVALIDATED.register(lambda: fired.append(True))
    yield fired
    registration.unregister()


def test_download_media_returns_what_was_downloaded(tmp_path, fake_main_loop, invalidations):
    media = FakeMedia(str(tmp_path))

    paths = download_media({"good": "url", "no-url": "", "broken": "broken", "gone": "missing"}, media)
    fake_main_loop.run_pending()

    assert paths == {"good": str(tmp_path / "good.png")}
    assert invalidations == [True]


def test_nothing_downloaded_leaves_the_cache_alone(tmp_path, fake_main_loop, invalidations):
    assert download_media({"gone": "missing"}, FakeMedia(str(tmp_path))) == {}
    fake_main_loop.run_pending()
    assert invalidations == []


def test_egs_box_art_gets_its_logo_overlaid(tmp_path, monkeypatch):
    logo_dir = tmp_path / "logos"
    logo_dir.mkdir()
    monkeypatch.setattr("lutris.services.egs.EGS_LOGO_PATH", str(logo_dir))
    monkeypatch.setattr(DieselGameBoxTall, "dest_path", str(tmp_path / "boxes"))
    media = DieselGameBoxTall()
    Image.new("RGB", (400, 534), "black").save(tmp_path / "boxes" / "game.jpg")
    Image.new("RGBA", (300, 300), "white").save(logo_dir / "game.png")

    media.render()

    with Image.open(tmp_path / "boxes" / "game.jpg") as rendered:
        assert rendered.size == DieselGameBoxTall.remote_size
        middle = cast(tuple[int, int, int], rendered.getpixel((100, 133)))
        corner = cast(tuple[int, int, int], rendered.getpixel((2, 2)))
    assert middle[0] > 200  # The logo, scaled down into the middle
    assert corner[0] < 50
