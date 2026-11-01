"""Which games a view shows, loaded from the database and the services.

The window decides what the filters mean (see lutris.gui.game_filter) and how to sort (see
lutris.gui.game_sort); this module takes those decisions and produces the list of database game
dictionaries for a view. It reads the databases and the service objects, but no Gtk object, so
the sourcing can be tested with the databases patched.
"""

from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from lutris import services, settings
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import saved_searches as saved_searches_db
from lutris.database.services import ServiceGameCollection
from lutris.exceptions import InvalidSearchTermError
from lutris.gui import game_filter, game_sort
from lutris.gui.game_filter import FilterValues
from lutris.search import GameSearch
from lutris.util.path_cache import MISSING_GAMES


class ViewSortSettings(NamedTuple):
    """The view settings that drive sorting, as read from the window."""

    sorting: str
    reverse_order: bool
    installed_first: bool


class GameSourceContext(NamedTuple):
    """Everything the sourcing needs for a single load. It is plain data and callables, so a
    test can build one without a window."""

    filters: FilterValues
    search: GameSearch
    service: Any
    sort_settings: ViewSortSettings
    running_ids: Callable[[], Sequence[str]]


def combine_games(service_game: dict, lutris_game: dict | None) -> dict:
    """Injects the Lutris game information into a service game."""
    if lutris_game and service_game["appid"] == lutris_game["service_id"]:
        for field in ("platform", "runner", "installed_at", "lastplayed", "playtime", "installed"):
            service_game[field] = lutris_game[field]
        service_game["year"] = service_game["year"] if "year" in service_game else lutris_game["year"]
    return service_game


def apply_view_sort(items: Sequence[Any], context: GameSourceContext, resolver: Callable[[Any], Any] = lambda i: i):
    """Sorts a list of items for the sort settings of the view; see game_sort.apply_view_sort."""
    return game_sort.apply_view_sort(
        items,
        context.sort_settings.sorting,
        context.sort_settings.reverse_order,
        context.sort_settings.installed_first,
        context.service,
        resolver,
    )


def filter_games(games: Sequence[Any], context: GameSourceContext) -> list:
    """Filters games by the filters of the view: the installed and text filters, and the
    hidden games category."""
    return list(game_filter.filter_games(games, [game_filter.build_search(context.search, context.filters)]))


def get_running_games(context: GameSourceContext) -> list:
    """Returns the games currently running."""
    games = games_db.get_games_by_ids(context.running_ids())
    return apply_view_sort(filter_games(games, context), context)


def get_uncategorized_games(context: GameSourceContext) -> list:
    """Returns the games not in any category."""
    games = filter_games(categories_db.get_uncategorized_games(), context)
    return apply_view_sort(games, context)


def get_missing_games(context: GameSourceContext) -> list:
    """Returns the games whose install location can no longer be found."""
    games = games_db.get_games_by_ids(MISSING_GAMES.missing_game_ids)
    return apply_view_sort(filter_games(games, context), context)


def get_recent_games(context: GameSourceContext) -> list:
    """Returns recently installed or played games, most recent first."""
    games = filter_games(games_db.get_games(filters={"installed": "1"}), context)
    return sorted(games, key=lambda game: max(game["installed_at"] or 0, game["lastplayed"] or 0), reverse=True)


# The dynamic categories a view knows, and the function that loads each one.
DYNAMIC_CATEGORIES: dict[str, Callable[[GameSourceContext], list]] = {
    "recent": get_recent_games,
    "missing": get_missing_games,
    "running": get_running_games,
    ".uncategorized": get_uncategorized_games,
}

# The dynamic categories that honor the user's sort settings; the others have a fixed order.
SORTABLE_DYNAMIC_CATEGORIES = {".uncategorized", "missing", "running"}


def get_service_games(context: GameSourceContext, service_id: str) -> list:
    """Returns the games of the service indicated, combined with their Lutris counterparts."""
    service = context.service
    service_games = ServiceGameCollection.get_for_service(service_id)
    for game in service_games:
        game["year"] = service.get_game_release_year(game)

    if service_id == "lutris":
        lutris_games = {g["slug"]: g for g in games_db.get_games()}
    else:
        lutris_games = {g["service_id"]: g for g in games_db.get_games(filters={"service": service.id})}

    return filter_games(
        [
            combine_games(game, lutris_games.get(game["appid"]))
            for game in apply_view_sort(service_games, context, lambda game: lutris_games.get(game["appid"]) or game)
        ],
        context,
    )


def get_games_from_filters(context: GameSourceContext) -> list:
    """Returns the list of games for the current filters of the view."""
    filters = context.filters
    service_id = filters.service

    if service_id in services.SERVICES:
        if context.service.online and not context.service.is_authenticated():
            return []
        return get_service_games(context, service_id)

    if filters.dynamic_category in DYNAMIC_CATEGORIES:
        return DYNAMIC_CATEGORIES[filters.dynamic_category](context)

    search = context.search
    category = filters.category
    searches = [search]

    saved_search = filters.saved_search
    if saved_search:
        saved_search_found = saved_searches_db.get_saved_search_by_name(saved_search)

        if saved_search_found:
            try:
                searches.append(GameSearch(saved_search_found.search, service=None))
                category = "all"
            except InvalidSearchTermError:
                pass

    included = [category] if category != "all" else None
    excluded = (
        [".hidden"] if category != ".hidden" and not any(s for s in searches if s.has_component("hidden")) else []
    )
    category_game_ids = categories_db.get_game_ids_for_categories(included, excluded)

    sql_filters = game_filter.get_sql_filters(filters, search)
    excludes = {}

    if category == "all" and not service_id:
        excluded_services = set(
            s.casefold()
            for s in services.SERVICES.keys()
            if not settings.read_bool_setting(s + "_in_games_view", default=True, section="services")
        )
        if excluded_services:
            excludes["service"] = excluded_services

    games = games_db.get_games(filters=sql_filters, excludes=excludes)
    games = game_filter.filter_games([game for game in games if game["id"] in category_game_ids], searches)
    return apply_view_sort(games, context)
