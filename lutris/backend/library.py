"""Calls that read the library the way its views show it: which games a view
lists, in what order, and what each row says about its game."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lutris import settings
from lutris.backend.models import LibraryGame
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import saved_searches as saved_searches_db
from lutris.database.services import ServiceGameCollection
from lutris.exceptions import InvalidSearchTermError
from lutris.runners import get_runner_human_name
from lutris.search import GameSearch
from lutris.search_predicate import NotPredicate
from lutris.services import SERVICES
from lutris.services.base import BaseService, OnlineService
from lutris.util.path_cache import MISSING_GAMES
from lutris.util.strings import get_natural_sort_key

# The dynamic categories query_games() knows, and those whose games are listed in
# the view's sort order (the recent games are always the latest first)
DYNAMIC_CATEGORIES = ("recent", "missing", "running", ".uncategorized")
SORTABLE_DYNAMIC_CATEGORIES = ("missing", "running", ".uncategorized")

# Fields of a library game that are copied into the row of the service game it was
# installed from
_COMBINED_FIELDS = ("platform", "runner", "installed_at", "lastplayed", "playtime", "installed")


@dataclass(frozen=True)
class LibrarySort:
    """How a view orders its games: by "name", "year", "lastplayed", "installed_at" or
    "playtime", and whether installed games come first, whichever way it sorts."""

    key: str = "name"
    reverse: bool = False
    installed_first: bool = True


@dataclass(frozen=True)
class LibraryQuery:
    """What a library view shows: the sidebar row it's for (at most one of category,
    saved_search, dynamic_category, service, runner and platform), the search text,
    and whether only installed games show."""

    text: str = ""
    # A category's name, or "all", "favorite" or ".hidden"
    category: str | None = None
    saved_search: str | None = None
    # One of DYNAMIC_CATEGORIES
    dynamic_category: str | None = None
    # A service's id; its view lists the games it offers rather than the library's
    service: str | None = None
    runner: str | None = None
    platform: str | None = None
    installed_only: bool = False
    # The games running now, for the "running" dynamic category
    running_game_ids: tuple[str, ...] = ()
    sort: LibrarySort = field(default_factory=LibrarySort)


async def query_games(query: LibraryQuery) -> list[LibraryGame]:
    """Return the games a view shows, in order. A service's view is empty while its
    account is logged out."""
    return await asyncio.to_thread(_query_games, query)


async def has_uninstalled_games() -> bool:
    """True if the library has a game that isn't installed."""
    return bool(games_db.get_game_count("installed", "0"))


async def has_hidden_games() -> bool:
    """True if any game is in the .hidden category."""
    return bool(categories_db.get_game_ids_for_categories([".hidden"]))


async def get_library_game(game_id: str, service: str | None = None) -> LibraryGame | None:
    """Return the row for a library game; or, given a service's id, the row in that
    service's view for the game it was installed from. None if there's no such row."""
    db_game = games_db.get_game_by_field(game_id, "id")
    if not db_game:
        return None
    if not service:
        return _to_library_game(db_game)
    if service not in SERVICES or db_game.get("service") != service or not db_game.get("service_id"):
        return None
    service_game = ServiceGameCollection.get_game(service, db_game["service_id"])
    if not service_game:
        return None
    service_obj = SERVICES[service]()
    service_game["year"] = service_obj.get_game_release_year(service_game)
    installed_game = games_db.get_game_for_service(service, str(service_game["appid"]))
    return _to_library_game(service_game, service_obj, installed_game)


async def format_search(text: str, service: str | None = None) -> str:
    """Return a search's text in its standard form, as saved searches store it; service
    is the id of the service whose view it's for, if any."""
    return str(GameSearch(text, SERVICES[service]() if service in SERVICES else None))


async def search_mentions(text: str, tag: str) -> bool:
    """True if a search's text uses a tag, such as "hidden" or "installed"; a view then
    leaves showing those games to the search."""
    return GameSearch(text).has_component(tag)


def _query_games(query: LibraryQuery) -> list[LibraryGame]:
    if query.service in SERVICES:
        service = SERVICES[query.service]()
        if isinstance(service, OnlineService) and not service.is_authenticated():
            return []
        return _get_service_games(query, query.service, service)

    if query.dynamic_category in DYNAMIC_CATEGORIES:
        return [_to_library_game(db_game) for db_game in _get_dynamic_category_games(query)]

    search = _get_game_search(query)
    category = query.category or "all"
    searches = [search]

    if query.saved_search:
        saved_search = saved_searches_db.get_saved_search_by_name(query.saved_search)
        if saved_search:
            try:
                searches.append(GameSearch(saved_search.search, service=None))
                category = "all"
            except InvalidSearchTermError:
                pass

    included = [category] if category != "all" else None
    excluded = [".hidden"] if category != ".hidden" and not any(s.has_component("hidden") for s in searches) else []
    category_game_ids = set(categories_db.get_game_ids_for_categories(included, excluded))

    filters = {}
    if query.runner:
        filters["runner"] = query.runner
    if query.platform:
        filters["platform"] = query.platform
    if query.installed_only and not search.has_component("installed"):
        filters["installed"] = "1"

    excludes = {}
    if query.category == "all":
        excluded_services = {
            service_id.casefold()
            for service_id in SERVICES
            if not settings.read_bool_setting(service_id + "_in_games_view", default=True, section="services")
        }
        if excluded_services:
            excludes["service"] = excluded_services

    # The text search isn't done in SQL, which is too literal (accent sensitive, for one)
    db_games = games_db.get_games(filters=filters, excludes=excludes)
    db_games = _filter_games(query, [g for g in db_games if g["id"] in category_game_ids], searches)
    return [_to_library_game(db_game) for db_game in _sort_games(query.sort, db_games)]


def _get_dynamic_category_games(query: LibraryQuery) -> list[dict[str, Any]]:
    if query.dynamic_category == "recent":
        db_games = _filter_games(query, games_db.get_games(filters={"installed": "1"}))
        return sorted(db_games, key=lambda game: max(game["installed_at"] or 0, game["lastplayed"] or 0), reverse=True)
    if query.dynamic_category == "missing":
        db_games = games_db.get_games_by_ids(MISSING_GAMES.missing_game_ids)
    elif query.dynamic_category == "running":
        db_games = games_db.get_games_by_ids(query.running_game_ids)
    else:
        db_games = categories_db.get_uncategorized_games()
    return _sort_games(query.sort, _filter_games(query, db_games))


def _get_game_search(query: LibraryQuery, service: BaseService | None = None) -> GameSearch:
    return GameSearch(query.text, service)


def _filter_games(
    query: LibraryQuery,
    db_games: list[dict[str, Any]],
    searches: list[GameSearch] | None = None,
    service: BaseService | None = None,
) -> list[dict[str, Any]]:
    """Return the games that match the searches given, or else the query's search with
    its installed and hidden filters."""
    if searches is None:
        search = _get_game_search(query, service)
        if query.installed_only and not search.has_component("installed"):
            search = search.with_predicate(search.get_installed_predicate(installed=True))
        if (query.category or "all") != ".hidden" and not search.has_component("hidden"):
            search = search.with_predicate(NotPredicate(search.get_category_predicate(".hidden")))
        searches = [search]

    to_apply = [search for search in searches if not search.is_empty]
    if not to_apply:
        return db_games
    return [game for game in db_games if all(search.matches(game) for search in to_apply)]


def _get_service_games(query: LibraryQuery, service_id: str, service: BaseService) -> list[LibraryGame]:
    service_games = ServiceGameCollection.get_for_service(service_id)
    for service_game in service_games:
        service_game["year"] = service.get_game_release_year(service_game)

    if service_id == "lutris":
        lutris_games = {g["slug"]: g for g in games_db.get_games()}
    else:
        lutris_games = {g["service_id"]: g for g in games_db.get_games(filters={"service": service_id})}
    installed_games = games_db.get_all_installed_game_for_service(service_id)

    def get_sort_data(service_game: dict[str, Any]) -> dict[str, Any]:
        return lutris_games.get(service_game["appid"]) or service_game

    combined = [
        _combine_games(service_game, lutris_games.get(service_game["appid"]))
        for service_game in _sort_games(query.sort, service_games, get_sort_data, service)
    ]
    return [
        _to_library_game(game, service, installed_games.get(game["appid"]))
        for game in _filter_games(query, combined, service=service)
    ]


def _combine_games(service_game: dict[str, Any], lutris_game: dict[str, Any] | None) -> dict[str, Any]:
    """Copy what the library knows about a game installed from a service into the
    service's row for it."""
    if lutris_game and service_game["appid"] == lutris_game["service_id"]:
        for name in _COMBINED_FIELDS:
            service_game[name] = lutris_game[name]
        service_game["year"] = service_game["year"] if "year" in service_game else lutris_game["year"]
    return service_game


def _to_library_game(
    game: dict[str, Any], service: BaseService | None = None, installed_game: dict[str, Any] | None = None
) -> LibraryGame:
    """Return the row for a library game, or a service game together with the library
    game installed from it, if any, which provides what the service doesn't know."""
    is_service_game = "service_id" not in game

    def get(key: str) -> Any:
        if key in game:
            return game[key]
        return installed_game.get(key) if installed_game else None

    if is_service_game:
        view_id = game.get("appid") or game["slug"]
        installed_data = game if "installed" in game else installed_game
    else:
        view_id = game["id"]
        installed_data = game
    installed = bool(installed_data and installed_data.get("installed") and installed_data.get("runner"))

    platform = get("platform")
    if not platform and game.get("service") in SERVICES:
        platforms = (service or SERVICES[game["service"]]()).get_game_platforms(game)
        platform = ", ".join(platforms) if platforms else None

    runner = get("runner") or ""
    return LibraryGame(
        id=str(view_id),
        game_id=str(game["id"]) if not is_service_game else (str(installed_game["id"]) if installed_game else None),
        name=game["name"] or "",
        sortname=get("sortname") or "",
        slug=game["slug"] or "",
        year=_to_int(get("year")),
        runner=runner or None,
        runner_name=get_runner_human_name(runner) or None,
        platform=platform or None,
        installed=installed,
        installed_at=_to_int(get("installed_at")),
        lastplayed=_to_int(get("lastplayed")),
        playtime=_to_float(get("playtime")),
        service=game.get("service") or None,
        service_id=game.get("service_id") or None,
        appid=game.get("appid") or None,
        icon=game.get("icon") or None,
    )


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value else None
    except TypeError, ValueError:
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value else None
    except TypeError, ValueError:
        return None


def _sort_games(
    sort: LibrarySort,
    items: list[dict[str, Any]],
    get_data: Any = lambda item: item,
    service: BaseService | None = None,
) -> list[dict[str, Any]]:
    """Sort games, given as database rows or as items get_data finds the row for. Installed
    games come first, even in a descending sort, if sort.installed_first is set, and
    names sort naturally, so that 'Mega slap battler 20' comes after 'Mega slap battler 3'."""
    sort_defaults = {
        "name": "",
        "year": 0,
        "lastplayed": 0.0,
        "installed_at": 0.0,
        "playtime": 0.0,
    }

    def convert_value(value: Any) -> Any:
        """Converts value to the type the sort needs, or returns None if it can't."""
        try:
            if not value:
                return None
            if sort.key == "name":
                return str(value)
            if sort.key == "year":
                # Years can take many forms! We'll try to convert as best we can.
                if isinstance(value, datetime):
                    return int(value.year)
                try:
                    return int(value)
                except ValueError:
                    return int(datetime.strptime(str(value), "%Y-%m-%d").year)
            return float(value)
        except ValueError:
            return None

    def get_sort_default(item: dict[str, Any]) -> Any:
        """Returns the value to use when the item has none; a service may know it."""
        if sort.key == "year" and service:
            service_year = convert_value(service.get_game_release_date(item))
            if service_year:
                return service_year
        # Users may have obsolete sort settings, so we tolerate them, treating them all as blank
        return sort_defaults.get(sort.key, "")

    def extend_value(value: Any) -> Any:
        """Expands the value to sort by to a more complex form, for smarter sorting."""
        if sort.key == "name":
            return get_natural_sort_key(value)
        if sort.key == "year":
            contains_year = bool(value)
            if sort.reverse:
                contains_year = not contains_year
            return contains_year, value
        return value

    def get_sort_value(item: dict[str, Any]) -> Any:
        db_game = get_data(item)
        if not db_game:
            installation_flag = False
            value = None
        else:
            installation_flag = bool(db_game.get("installed"))
            # A name sort uses the sort name, if there is one
            if sort.key == "name":
                value = db_game.get("sortname") or db_game.get("name")
            else:
                value = db_game.get(sort.key)

        value = extend_value(convert_value(value) or get_sort_default(item))

        if sort.installed_first:
            # Installed games come first, even in a descending sort
            if sort.reverse:
                installation_flag = not installation_flag
            if sort.key == "name":
                installation_flag = not installation_flag
            return installation_flag, value
        return value

    reverse = sort.reverse if sort.key == "name" else not sort.reverse
    return sorted(items, key=get_sort_value, reverse=reverse)
