"""The backend's game calls return plain data about the library."""

import asyncio
import dataclasses

import pytest

from lutris import settings
from lutris.backend import game_maintenance, games, preferences, runners, services
from lutris.backend.models import GameInfo
from lutris.database import games as games_db
from lutris.database import sql
from lutris.database.services import ServiceGameCollection
from lutris.exceptions import GameConfigError
from lutris.game import Game
from lutris.util.test_config import setup_test_environment

setup_test_environment()


@pytest.fixture
def library():
    """Two games in the test library, one of them installed from a service."""
    game_ids = [
        games_db.add_game(
            name="Backend Installed",
            slug="backend-installed",
            runner="linux",
            installed=1,
            service="steam",
            service_id="4242",
            playtime=1.5,
        ),
        games_db.add_game(name="Backend Not Installed", slug="backend-not-installed", runner="wine", installed=0),
    ]
    yield [str(game_id) for game_id in game_ids]
    for game_id in game_ids:
        games_db.delete_game(game_id)


def test_games_come_as_plain_data(library):
    installed_id, _other_id = library
    game = asyncio.run(games.get_game(installed_id))

    assert isinstance(game, GameInfo)
    assert (game.name, game.slug, game.runner, game.installed, game.playtime) == (
        "Backend Installed",
        "backend-installed",
        "linux",
        True,
        1.5,
    )
    # Plain data all the way down, so it can cross a process boundary
    for value in dataclasses.asdict(game).values():
        assert value is None or isinstance(value, (str, int, float, bool))


def test_installed_games_can_be_listed_alone(library):
    installed_id, other_id = library
    all_ids = {game.id for game in asyncio.run(games.list_games())}
    installed_ids = {game.id for game in asyncio.run(games.list_games(installed_only=True))}

    assert {installed_id, other_id} <= all_ids
    assert installed_id in installed_ids
    assert other_id not in installed_ids


def test_games_are_found_by_id_or_slug(library):
    installed_id, _other_id = library
    by_id = asyncio.run(games.find_game(installed_id))
    by_slug = asyncio.run(games.find_game("backend-installed"))
    assert by_id and by_id.slug == "backend-installed"
    assert by_slug and by_slug.id == installed_id
    assert asyncio.run(games.find_game("no-such-game")) is None
    assert [game.slug for game in asyncio.run(games.find_games_by_slug("backend-not"))] == ["backend-not-installed"]


def test_service_games_know_whether_they_are_installed(library, monkeypatch):
    service_games = [
        {"id": 1, "service": "steam", "appid": "4242", "name": "Installed", "slug": "a", "details": "{}"},
        {"id": 2, "service": "steam", "appid": "7", "name": "Not installed", "slug": "b", "details": None},
    ]
    monkeypatch.setattr(ServiceGameCollection, "get_for_service", classmethod(lambda _cls, _service: service_games))

    listed = asyncio.run(services.list_service_games("steam"))
    assert [(game.appid, game.installed) for game in listed] == [("4242", True), ("7", False)]
    assert [game.appid for game in asyncio.run(services.list_service_games("steam", installed_only=True))] == ["4242"]


def test_retired_flatpak_integration_leaves_existing_game_records() -> None:
    game_id = str(
        games_db.add_game(
            name="Previous Flatpak Game",
            slug="previous-flatpak-game",
            runner="flatpak",
            service="flathub",
            configpath="previous-flatpak-game",
            installed=1,
        )
    )
    service_id = sql.db_insert(
        settings.DB_PATH,
        "service_games",
        {"service": "flathub", "appid": "org.example.Game", "name": "Previous Flatpak Game", "slug": "flatpak-test"},
    )
    try:
        assert "flatpak" not in asyncio.run(runners.list_runners())
        assert "flathub" not in {source.id for source in asyncio.run(preferences.list_sources())}
        assert not asyncio.run(services.list_service_games("flathub"))
        assert "flathub" not in {game.service for game in asyncio.run(services.list_service_games())}
        assert asyncio.run(games.get_game(game_id)) is not None
        info = asyncio.run(game_maintenance.get_maintenance_info(game_id))
        assert info.files_unavailable_reason == "This installation is managed outside Lutris."
        with pytest.raises(GameConfigError, match="Flatpak runner has been removed"):
            Game(game_id).check_launchable()
    finally:
        sql.db_delete(settings.DB_PATH, "service_games", "id", service_id)
        games_db.delete_game(game_id)
