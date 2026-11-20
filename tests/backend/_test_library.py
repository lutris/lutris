"""The library views' games, as lutris.backend.library selects, orders and describes them."""

import asyncio

import pytest

from lutris.backend import library
from lutris.backend.library import LibraryQuery, LibrarySort
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.util.test_config import setup_test_environment

setup_test_environment()

# Only the games these tests add are looked at, whatever else the test library has
PREFIX = "library-test-"


def query(**values) -> list[str]:
    """The slugs of this test's games a query returns, in order."""
    games = asyncio.run(library.query_games(LibraryQuery(**values)))
    return [game.slug for game in games if game.slug.startswith(PREFIX)]


@pytest.fixture
def games():
    """Four games: two installed, one hidden, one favorite, with distinct play data."""
    specs = [
        ("Game 10", "linux", 1, {"lastplayed": 300, "playtime": 1.0, "year": 2010}),
        ("Game 9", "wine", 1, {"lastplayed": 100, "playtime": 5.0, "year": 2009}),
        ("Hidden Game", "linux", 1, {}),
        ("Uninstalled Game", "linux", 0, {"year": 2020}),
    ]
    ids = {}
    for name, runner, installed, extra in specs:
        slug = PREFIX + name.lower().replace(" ", "-")
        ids[slug] = str(games_db.add_game(name=name, slug=slug, runner=runner, installed=installed, **extra))
    hidden = categories_db.get_category_by_name(".hidden") or {"id": categories_db.add_category(".hidden")}
    favorite = categories_db.get_category_by_name("favorite") or {"id": categories_db.add_category("favorite")}
    categories_db.add_game_to_category(ids[PREFIX + "hidden-game"], int(hidden["id"]))
    categories_db.add_game_to_category(ids[PREFIX + "game-9"], int(favorite["id"]))
    yield ids
    for game_id in ids.values():
        for category in categories_db.get_categories_in_game(game_id):
            found = categories_db.get_category_by_name(category)
            if found:
                categories_db.remove_category_from_game(game_id, int(found["id"]))
        games_db.delete_game(game_id)


def test_all_games_hide_hidden_ones_and_sort_names_naturally(games):
    assert query(category="all") == [PREFIX + "game-9", PREFIX + "game-10", PREFIX + "uninstalled-game"]


def test_hidden_games_show_in_their_category_or_when_searched_for(games):
    assert query(category=".hidden") == [PREFIX + "hidden-game"]
    assert PREFIX + "hidden-game" in query(category="all", text="hidden:yes")


def test_installed_only(games):
    assert query(category="all", installed_only=True) == [PREFIX + "game-9", PREFIX + "game-10"]


def test_categories_runners_and_text(games):
    assert query(category="favorite") == [PREFIX + "game-9"]
    assert query(runner="wine") == [PREFIX + "game-9"]
    assert query(category="all", text="uninstalled") == [PREFIX + "uninstalled-game"]


def test_sorting(games):
    by_playtime = LibrarySort(key="playtime", reverse=False, installed_first=True)
    assert query(category="all", sort=by_playtime) == [
        PREFIX + "game-9",
        PREFIX + "game-10",
        PREFIX + "uninstalled-game",
    ]
    by_year = LibrarySort(key="year", reverse=False, installed_first=False)
    assert query(category="all", sort=by_year) == [PREFIX + "uninstalled-game", PREFIX + "game-10", PREFIX + "game-9"]


def test_recent_games_are_the_latest_played_first(games):
    assert query(dynamic_category="recent") == [PREFIX + "game-10", PREFIX + "game-9"]


def test_running_games_are_the_ones_given(games):
    assert query(dynamic_category="running", running_game_ids=(games[PREFIX + "game-10"],)) == [PREFIX + "game-10"]


def test_rows_describe_their_games(games):
    rows = asyncio.run(library.query_games(LibraryQuery(category="all", runner="wine")))
    row = next(row for row in rows if row.slug == PREFIX + "game-9")
    assert (row.id, row.game_id, row.name, row.runner, row.runner_name, row.installed, row.year) == (
        games[PREFIX + "game-9"],
        games[PREFIX + "game-9"],
        "Game 9",
        "wine",
        "Wine",
        True,
        2009,
    )
    assert asyncio.run(library.get_library_game(games[PREFIX + "game-9"])) == row


def test_a_service_view_merges_in_the_games_installed_from_it(games, monkeypatch):
    game_id = games[PREFIX + "game-10"]
    games_db.update_existing(id=game_id, service="xdg", service_id="game10.desktop")
    service_games = [
        {
            "id": 1,
            "service": "xdg",
            "appid": "game10.desktop",
            "name": "Game 10",
            "slug": PREFIX + "s10",
            "details": "{}",
        },
        {
            "id": 2,
            "service": "xdg",
            "appid": "other.desktop",
            "name": "Other",
            "slug": PREFIX + "other",
            "details": "{}",
        },
    ]
    monkeypatch.setattr(
        ServiceGameCollection, "get_for_service", classmethod(lambda _cls, _service: [dict(g) for g in service_games])
    )
    monkeypatch.setattr(
        ServiceGameCollection, "get_game", classmethod(lambda _cls, _service, appid: dict(service_games[0]))
    )

    rows = asyncio.run(library.query_games(LibraryQuery(service="xdg")))
    merged, other = (next(r for r in rows if r.appid == appid) for appid in ("game10.desktop", "other.desktop"))
    assert (merged.id, merged.game_id, merged.installed, merged.runner, merged.playtime) == (
        "game10.desktop",
        game_id,
        True,
        "linux",
        1.0,
    )
    assert (other.game_id, other.installed, other.runner) == (None, False, None)
    assert [r.appid for r in rows if r.slug.startswith(PREFIX)] == ["game10.desktop", "other.desktop"]

    updated = asyncio.run(library.get_library_game(game_id, "xdg"))
    assert updated and (updated.id, updated.installed) == ("game10.desktop", True)


def test_search_text_helpers():
    assert asyncio.run(library.search_mentions("hidden:yes doom", "hidden"))
    assert not asyncio.run(library.search_mentions("doom", "hidden"))
    assert asyncio.run(library.format_search("doom installed:yes")) == "doom installed:yes"


def test_a_game_is_in_a_view_if_its_query_lists_it(games):
    game_id = games[PREFIX + "game-9"]

    def in_view(**values) -> bool:
        return asyncio.run(library.is_game_in_view(LibraryQuery(**values), game_id))

    assert in_view(category="all")
    assert in_view(category="favorite")
    assert in_view(category="all", text="game 9")
    assert not in_view(category="all", text="uninstalled")
    assert not in_view(category=".hidden")
    assert not in_view(runner="linux")
    assert in_view(dynamic_category="recent")
    assert not in_view(dynamic_category="running")
    assert in_view(service="xdg")  # Service views aren't checked
