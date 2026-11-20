"""Prepare chosen images with QImage and store them as a game's artwork."""

import asyncio
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QGuiApplication, QImage

from lutris.backend import game_artwork
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.qt.delegates import PromptController
from lutris.qt.game_artwork import GameArtworkController, prepare_image
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisIcon
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()


def save(path: Path, width: int, height: int, transparent: bool = False) -> str:
    image = QImage(width, height, QImage.Format.Format_ARGB32 if transparent else QImage.Format.Format_RGB32)
    image.fill(QColor(0, 0, 0, 0) if transparent else QColor("teal"))
    assert image.save(str(path))
    return str(path)


def test_images_are_scaled_to_fit_and_converted(qt_application: QGuiApplication, tmp_path: Path) -> None:
    cover = prepare_image(save(tmp_path / "large.bmp", 1200, 1800), "cover")
    try:
        prepared = QImage(cover)
        assert cover.endswith(".jpg") and (prepared.width(), prepared.height()) == (600, 900)
    finally:
        Path(cover).unlink()

    banner = prepare_image(save(tmp_path / "small.png", 200, 100, transparent=True), "banner")
    try:
        # Small images keep their size, and transparency keeps them PNG
        assert banner.endswith(".png") and QImage(banner).size().width() == 200
    finally:
        Path(banner).unlink()

    icon = prepare_image(save(tmp_path / "icon.jpg", 512, 512), "icon")
    try:
        assert icon.endswith(".png") and QImage(icon).width() == 256
    finally:
        Path(icon).unlink()

    (tmp_path / "text.png").write_text("not an image", encoding="utf-8")
    with pytest.raises(LutrisError):
        prepare_image(str(tmp_path / "text.png"), "cover")


@pytest.fixture
def game_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop) -> Iterator[str]:
    for media_class, folder in ((LutrisCoverart, "coverart"), (LutrisBanner, "banners"), (LutrisIcon, "icons")):
        monkeypatch.setattr(media_class, "dest_path", str(tmp_path / folder))
    monkeypatch.setattr(game_artwork.system, "update_desktop_icons", lambda: None)
    monkeypatch.setattr(game_artwork, "forget_misses", lambda slug: None)
    monkeypatch.setattr(game_artwork, "fetch_game_artwork", lambda slug: 0)
    new_id = str(games_db.add_game(name="Qt Artwork", slug="qt-artwork-game", runner="linux", installed=1))
    yield new_id
    games_db.delete_game(new_id)
    fake_main_loop.run_pending()


def test_the_controller_stores_and_resets_a_chosen_cover(
    qt_application: QGuiApplication, game_id: str, tmp_path: Path
) -> None:
    errors: list[BaseException] = []
    prompts = PromptController()
    prompts.error = errors.append  # type: ignore[method-assign]
    controller = GameArtworkController(prompts, prompts)

    async def wait(ready: object) -> None:
        for _ in range(100):
            qt_application.processEvents()
            if callable(ready) and ready():
                return
            await asyncio.sleep(0.02)
        pytest.fail(f"The artwork did not get there: {errors}")

    def cover() -> dict[str, Any]:
        return next(image for image in controller.property("images") if image["kind"] == "cover")

    leftovers = set(Path(tempfile.gettempdir()).glob("lutris-artwork-*"))

    async def run() -> None:
        controller.open_game(game_id)
        await wait(lambda: len(controller._images) == 3)
        assert cover()["url"] == QUrl() and not cover()["custom"]

        controller.choose_file("cover", QUrl.fromLocalFile(save(tmp_path / "chosen.bmp", 900, 1350)))
        await wait(lambda: bool(cover()["custom"]))
        stored = tmp_path / "coverart" / "qt-artwork-game.jpg"
        assert QImage(str(stored)).size().width() == 600
        assert cover()["url"].toLocalFile() == str(stored) and cover()["url"].query()
        # The prepared temporary file is gone
        assert set(Path(tempfile.gettempdir()).glob("lutris-artwork-*")) <= leftovers

        controller.reset("cover")
        await wait(lambda: not cover()["custom"])
        assert not stored.exists()

    asyncio.run(run())
    assert not errors
