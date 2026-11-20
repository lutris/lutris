"""Choose, replace and reset a game's own artwork."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lutris.artwork import steamgriddb
from lutris.backend import game_artwork
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisIcon
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()

PNG = b"\x89PNG\r\n\x1a\n" + b"png data"
JPEG = b"\xff\xd8\xff" + b"jpeg data"


@pytest.fixture
def game_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop) -> Iterator[str]:
    for media_class, folder in ((LutrisCoverart, "coverart"), (LutrisBanner, "banners"), (LutrisIcon, "icons")):
        monkeypatch.setattr(media_class, "dest_path", str(tmp_path / folder))
    monkeypatch.setattr(game_artwork.system, "update_desktop_icons", lambda: None)
    monkeypatch.setattr(game_artwork, "forget_misses", lambda slug: None)
    monkeypatch.delenv(steamgriddb.API_KEY_ENVIRONMENT, raising=False)
    new_id = str(games_db.add_game(name="Artwork Game", slug="custom-artwork-game", runner="linux", installed=1))
    yield new_id
    games_db.delete_game(new_id)
    fake_main_loop.run_pending()


def image(path: Path, content: bytes) -> str:
    path.write_bytes(content)
    return str(path)


def test_custom_artwork_replaces_the_automatic_one_until_reset(
    game_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched: list[str] = []

    def fetch(slug: str) -> int:
        fetched.append(slug)
        (tmp_path / "coverart" / f"{slug}.jpg").write_bytes(JPEG)
        return 1

    monkeypatch.setattr(game_artwork, "fetch_game_artwork", fetch)
    automatic = tmp_path / "coverart" / "custom-artwork-game.jpg"
    automatic.parent.mkdir()
    automatic.write_bytes(JPEG)

    async def run() -> None:
        cover = await game_artwork.set_custom_artwork(game_id, "cover", image(tmp_path / "mine.png", PNG))
        assert cover.custom and cover.path == str(tmp_path / "coverart" / "custom-artwork-game.png")
        # The automatic cover had another extension, and goes
        assert not automatic.exists()
        row = games_db.get_game_by_field(game_id, "id")
        assert row is not None and row["has_custom_coverart_big"] == 1

        reset = await game_artwork.reset_artwork(game_id, "cover")
        assert not reset.custom and reset.path == str(automatic)
        assert fetched == ["custom-artwork-game"]
        images = await game_artwork.get_game_artwork(game_id)
        assert [(item.kind, item.custom) for item in images] == [("cover", False), ("banner", False), ("icon", False)]

    asyncio.run(run())


def test_only_png_and_jpeg_are_stored_and_icons_must_be_png(game_id: str, tmp_path: Path) -> None:
    async def run() -> None:
        with pytest.raises(LutrisError, match="PNG or JPEG"):
            await game_artwork.set_custom_artwork(game_id, "banner", image(tmp_path / "text.png", b"not an image"))
        with pytest.raises(LutrisError, match="Icons must be PNG"):
            await game_artwork.set_custom_artwork(game_id, "icon", image(tmp_path / "icon.jpg", JPEG))
        with pytest.raises(LutrisError, match="Unknown kind"):
            await game_artwork.set_custom_artwork(game_id, "poster", image(tmp_path / "poster.png", PNG))
        icon = await game_artwork.set_custom_artwork(game_id, "icon", image(tmp_path / "icon.png", PNG))
        assert icon.path == str(tmp_path / "icons" / "lutris_custom-artwork-game.png")

    asyncio.run(run())


def test_choices_come_from_steamgriddb_and_are_downloaded(
    game_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        with pytest.raises(LutrisError, match="API key"):
            await game_artwork.list_steamgriddb_artwork(game_id, "cover")

    asyncio.run(run())

    class Client:
        def __init__(self, api_key: str) -> None:
            assert api_key == "key"

        def find_game(self, name: str, steam_appid: str = "") -> int:
            assert (name, steam_appid) == ("Artwork Game", "")
            return 7

        def grids(self, game_id: int, dimensions: str) -> list[dict[str, Any]]:
            if dimensions != "920x430,460x215":
                return []
            return [
                {"url": "https://sgdb/wide.jpg", "thumb": "https://sgdb/wide-thumb.jpg", "width": 920, "height": 430}
            ]

    class Response:
        content = JPEG

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setenv(steamgriddb.API_KEY_ENVIRONMENT, "key")
    monkeypatch.setattr(game_artwork, "SteamGridDB", Client)
    monkeypatch.setattr(game_artwork.requests, "get", lambda url, **_kwargs: Response())

    async def choose() -> None:
        choices = await game_artwork.list_steamgriddb_artwork(game_id, "banner")
        assert [(choice.thumbnail_url, choice.width, choice.height) for choice in choices] == [
            ("https://sgdb/wide-thumb.jpg", 920, 430)
        ]
        banner = await game_artwork.use_artwork_url(game_id, "banner", choices[0].url)
        assert banner.custom and banner.path and Path(banner.path).read_bytes() == JPEG

    asyncio.run(choose())
