"""Fetch library artwork from stores and SteamGridDB, with their web APIs faked."""

import asyncio
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from lutris import settings
from lutris.artwork import fetcher, steamgriddb, stores, sync_artwork
from lutris.backend import media
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisIcon
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()

PNG = b"\x89PNG\r\n\x1a\n" + b"png data"
JPEG = b"\xff\xd8\xff" + b"jpeg data"
STEAM_COVER = stores.STEAM_URL % ("620", "library_600x900_2x.jpg")
STEAM_HEADER = stores.STEAM_URL % ("620", "header.jpg")


@dataclass
class FakeResponse:
    status_code: int = 200
    content: bytes = b""
    data: Any = None

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        return self.data


@dataclass
class Web:
    """Images by URL, and SteamGridDB's answers by API path."""

    images: dict[str, bytes] = field(default_factory=dict)
    steamgriddb: dict[str, Any] = field(default_factory=dict)
    steamgriddb_status: int = 200
    fetched: list[str] = field(default_factory=list)
    queries: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def get(self, url: str, **_kwargs: Any) -> FakeResponse:
        self.fetched.append(url)
        if url in self.images:
            return FakeResponse(content=self.images[url])
        return FakeResponse(status_code=404)


@pytest.fixture
def web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop) -> Iterator[Web]:
    fake = Web()
    for media_class, folder in ((LutrisCoverart, "coverart"), (LutrisBanner, "banners"), (LutrisIcon, "icons")):
        monkeypatch.setattr(media_class, "dest_path", str(tmp_path / folder))
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv(steamgriddb.API_KEY_ENVIRONMENT, raising=False)
    monkeypatch.setattr(settings, "read_setting", lambda key, default="", section="lutris": default)
    monkeypatch.setattr(fetcher.requests, "get", fake.get)

    class Session:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            self.proxies: dict[str, str] = {}

        def get(self, url: str, params: dict[str, str] | None = None, **_kwargs: Any) -> FakeResponse:
            path = url.removeprefix(steamgriddb.API_URL)
            fake.queries.append((path, params or {}))
            if fake.steamgriddb_status != 200:
                return FakeResponse(status_code=fake.steamgriddb_status)
            key = path + ("?" + params["dimensions"] if params and "dimensions" in params else "")
            if key not in fake.steamgriddb:
                return FakeResponse(status_code=404)
            return FakeResponse(data={"success": True, "data": fake.steamgriddb[key]})

    monkeypatch.setattr(steamgriddb.requests, "Session", Session)
    yield fake
    # Leave no artwork announcement for other tests
    fake_main_loop.run_pending()


@pytest.fixture
def games() -> Iterator[list[str]]:
    ids: list[str] = []
    yield ids
    for game_id in ids:
        games_db.delete_game(game_id)


def add(games: list[str], name: str, slug: str, service: str = "", service_id: str = "") -> None:
    games.append(str(games_db.add_game(name=name, slug=slug, runner="linux", service=service, service_id=service_id)))


def misses(tmp_path: Path) -> dict[str, float]:
    return json.loads((tmp_path / "cache" / "artwork-misses.json").read_text(encoding="utf-8"))


def test_steam_games_use_steam_art_and_steamgriddb_icons(
    web: Web, games: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(steamgriddb.API_KEY_ENVIRONMENT, "key")
    add(games, "Portal 2", "artwork-portal-2", "steam", "620")
    web.images.update({STEAM_COVER: JPEG, STEAM_HEADER: PNG, "https://sgdb/icon.png": PNG})
    web.steamgriddb.update({"/games/steam/620": {"id": 5}, "/icons/game/5": [{"url": "https://sgdb/icon.png"}]})

    assert sync_artwork(["artwork-portal-2"]) == 3

    assert (tmp_path / "coverart" / "artwork-portal-2.jpg").read_bytes() == JPEG
    assert (tmp_path / "banners" / "artwork-portal-2.png").read_bytes() == PNG
    assert (tmp_path / "icons" / "lutris_artwork-portal-2.png").read_bytes() == PNG
    assert [path for path, _params in web.queries] == ["/games/steam/620", "/icons/game/5"]


def test_local_games_use_steamgriddb_grids_once_a_key_is_set(
    web: Web, games: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add(games, "Local Game", "artwork-local-game")
    assert sync_artwork(["artwork-local-game"]) == 0
    assert all(key.endswith(":store") for key in misses(tmp_path))
    assert sync_artwork(["artwork-local-game"]) == 0 and not web.fetched

    monkeypatch.setenv(steamgriddb.API_KEY_ENVIRONMENT, "key")
    web.steamgriddb.update(
        {
            "/search/autocomplete/Local%20Game": [{"id": 1, "name": "Local Game 2"}, {"id": 2, "name": "local game"}],
            "/grids/game/2?342x482,660x930": [{"url": "https://sgdb/cover.png"}],
            "/grids/game/2?920x430,460x215": [{"url": "https://sgdb/banner.jpg"}],
        }
    )
    web.images.update({"https://sgdb/cover.png": PNG, "https://sgdb/banner.jpg": JPEG})

    assert sync_artwork(["artwork-local-game"]) == 2
    assert (tmp_path / "coverart" / "artwork-local-game.png").exists()
    assert (tmp_path / "banners" / "artwork-local-game.jpg").exists()
    grid_queries = [params for path, params in web.queries if path.startswith("/grids/")]
    # No 2:3 grid, so the cover falls back to a near 2:3 one
    assert [params["dimensions"] for params in grid_queries] == ["600x900", "342x482,660x930", "920x430,460x215"]
    assert all(params["types"] == "static" and params["nsfw"] == "false" for params in grid_queries)
    assert "artwork-local-game:icon:steamgriddb" in misses(tmp_path)


def test_existing_artwork_is_never_replaced(web: Web, games: list[str], tmp_path: Path) -> None:
    add(games, "Portal 2", "artwork-custom", "steam", "620")
    custom = tmp_path / "coverart" / "artwork-custom.jpg"
    custom.parent.mkdir()
    custom.write_bytes(b"custom")
    web.images.update({STEAM_COVER: JPEG, STEAM_HEADER: JPEG})

    assert sync_artwork(["artwork-custom"]) == 1
    assert custom.read_bytes() == b"custom" and STEAM_COVER not in web.fetched


def test_a_rejected_key_records_no_steamgriddb_misses(
    web: Web, games: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(steamgriddb.API_KEY_ENVIRONMENT, "wrong")
    web.steamgriddb_status = 401
    add(games, "Local Game", "artwork-rejected")

    assert sync_artwork(["artwork-rejected"]) == 0
    assert not (tmp_path / "cache" / "artwork-misses.json").exists()


def test_gog_covers_come_from_gogs_game_database(
    web: Web, games: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add(games, "Gog Game", "artwork-gog", "gog", "1207658924")
    url_format = "https://images.gog.com/hash{formatter}.{ext}?namespace=gamesdb"

    def get(url: str, **kwargs: Any) -> FakeResponse:
        # Both modules share requests, so one fake answers the database and the images
        if url == stores.GOG_GAMESDB_URL % "1207658924":
            return FakeResponse(data={"game": {"vertical_cover": {"url_format": url_format}}})
        return web.get(url, **kwargs)

    monkeypatch.setattr(stores.requests, "get", get)
    monkeypatch.setattr(stores, "_service_details", lambda service, appid: {"image": "//images.gog/banner"})
    cover = "https://images.gog.com/hash_glx_vertical_cover.jpg?namespace=gamesdb"
    web.images.update({cover: JPEG, "https://images.gog/banner_392.jpg": JPEG})

    assert sync_artwork(["artwork-gog"]) == 2
    assert (tmp_path / "coverart" / "artwork-gog.jpg").exists() and (tmp_path / "banners" / "artwork-gog.jpg").exists()


def test_keys_are_checked_before_they_are_saved(web: Web, monkeypatch: pytest.MonkeyPatch) -> None:
    written: dict[str, object] = {}
    monkeypatch.setattr(settings, "write_setting", lambda key, value, section="lutris": written.update({key: value}))

    web.steamgriddb_status = 401
    with pytest.raises(LutrisError, match="rejected"):
        asyncio.run(media.set_steamgriddb_api_key("wrong"))
    assert not written

    web.steamgriddb_status = 200
    asyncio.run(media.set_steamgriddb_api_key(" right "))
    assert written == {steamgriddb.API_KEY_SETTING: "right"}
    settings_info = asyncio.run(media.get_artwork_settings())
    assert settings_info.steamgriddb_key_page == steamgriddb.API_KEY_PAGE


def test_steam_covers_fall_back_to_the_smaller_image(web: Web, games: list[str], tmp_path: Path) -> None:
    add(games, "Portal 2", "artwork-small-cover", "steam", "620")
    small_cover = stores.STEAM_URL % ("620", "library_600x900.jpg")
    web.images.update({small_cover: JPEG})

    assert sync_artwork(["artwork-small-cover"]) == 1
    assert web.fetched[:2] == [STEAM_COVER, small_cover]
    assert (tmp_path / "coverart" / "artwork-small-cover.jpg").read_bytes() == JPEG
