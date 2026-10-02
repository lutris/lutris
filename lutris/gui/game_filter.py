"""The rules that decide which games a view shows, and what to say when it shows none.

These are all pure functions; the state they read comes in as a FilterValues snapshot and the
searches they build are passed to them, so they can be tested without a window.
"""

from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from typing import Any, NamedTuple

from lutris.search import GameSearch
from lutris.search_predicate import NotPredicate


class SidebarSelection(NamedTuple):
    """The type and the id of the row selected in the sidebar; these are the name of the
    filter and its value, such as ('service', 'lutris') or ('dynamic_category', 'running')."""

    row_type: str
    row_id: str


class FilterValues:
    """The filters applied to a view, with the defaults applied, so that the rules below need
    not worry about which filters are set and which are not."""

    def __init__(self, filters: Mapping[str, Any]) -> None:
        self.text = filters.get("text") or ""
        self.installed = bool(filters.get("installed"))
        self.category = filters.get("category") or "all"
        self.dynamic_category = filters.get("dynamic_category")
        self.saved_search = filters.get("saved_search")
        self.service = filters.get("service")
        self.runner = filters.get("runner")
        self.platform = filters.get("platform")


class EmptyViewReason(Enum):
    """The reason a view is showing no games; this is what the window says when it is empty."""

    SPLASH = "splash"
    NO_GAMES = "no_games"
    NO_FAVORITES = "no_favorites"
    NO_HIDDEN_GAMES = "no_hidden_games"
    NO_INSTALLED_GAMES = "no_installed_games"
    NO_GAMES_MATCHING_TEXT = "no_games_matching_text"
    NO_FAVORITES_MATCHING_TEXT = "no_favorites_matching_text"
    NO_HIDDEN_MATCHING_TEXT = "no_hidden_matching_text"
    NO_INSTALLED_MATCHING_TEXT = "no_installed_matching_text"


def get_empty_view_reason(filters: FilterValues, has_uninstalled_games: bool) -> EmptyViewReason:
    """Returns why a view with these filters is empty, so the window can show the message that
    matches (the splash screen is one of the possibilities)."""
    if filters.text:
        if filters.category == "favorite":
            return EmptyViewReason.NO_FAVORITES_MATCHING_TEXT
        if filters.category == ".hidden":
            return EmptyViewReason.NO_HIDDEN_MATCHING_TEXT
        if filters.installed and has_uninstalled_games:
            return EmptyViewReason.NO_INSTALLED_MATCHING_TEXT
        return EmptyViewReason.NO_GAMES_MATCHING_TEXT

    if filters.category == "favorite":
        return EmptyViewReason.NO_FAVORITES
    if filters.category == ".hidden":
        return EmptyViewReason.NO_HIDDEN_GAMES
    if filters.installed and has_uninstalled_games:
        return EmptyViewReason.NO_INSTALLED_GAMES
    if not (filters.runner or filters.service or filters.platform or filters.dynamic_category):
        return EmptyViewReason.SPLASH
    return EmptyViewReason.NO_GAMES


def build_search(search: GameSearch, filters: FilterValues) -> GameSearch:
    """Returns 'search' with the predicates these filters call for added to it; these are the
    ones the game database on its own cannot apply, so filter_games() applies them instead."""
    if filters.installed and not search.has_component("installed"):
        search = search.with_predicate(search.get_installed_predicate(installed=True))

    if filters.category != ".hidden" and not search.has_component("hidden"):
        search = search.with_predicate(NotPredicate(search.get_category_predicate(".hidden")))

    return search


def filter_games(games: Sequence[Any], searches: Iterable[GameSearch]) -> Sequence[Any]:
    """Filters a list of games, which are database game dictionaries, by each of the searches
    given; a game must match all of them. Searches that have nothing to apply are skipped, so
    the games are returned unchanged if none of them can match anything."""
    to_apply = [search for search in searches if not search.is_empty]

    if not to_apply:
        return games

    def matches(game: Any) -> bool:
        for search in to_apply:
            if not search.matches(game):
                return False
        return True

    return [game for game in games if matches(game)]


def get_sql_filters(filters: FilterValues, search: GameSearch) -> dict[str, str]:
    """Returns the filters that can be handed to the games database itself, for the filters
    given.

    We omit the "text" search here because SQLite does a fairly literal search, which is
    accent sensitive. We'll do better with filter_games()."""
    sql_filters: dict[str, str] = {}
    if filters.runner:
        sql_filters["runner"] = filters.runner
    if filters.platform:
        sql_filters["platform"] = filters.platform
    if filters.installed and not search.has_component("installed"):
        sql_filters["installed"] = "1"

    return sql_filters


def is_game_displayed(
    selection: SidebarSelection | None, categories: Sequence[str], is_stopped: bool, enforce_hidden: bool
) -> bool:
    """Returns whether a game that is already in the view should stay there, given the row
    selected in the sidebar.

    A game that no longer belongs on the current page (because it was hidden, un-hidden,
    stopped, or added to another category) must be taken out of the view.

    The 'categories' are those of the game; 'is_stopped' tells if the game is not running, and
    'enforce_hidden' is False if the search itself is showing hidden games."""
    if not selection:
        return True

    row_type, row_id = selection

    # Stopped games do not get displayed on the running page
    if row_type == "dynamic_category" and row_id == "running" and is_stopped:
        return False

    # If the update took the row out of this view's category, we'll need
    # to update the view to reflect that.
    if row_type == "dynamic_category" and row_id in ("recent", "missing"):
        if enforce_hidden and ".hidden" in categories:
            return False
    elif row_type in ("category", "user_category", "saved_search"):
        if enforce_hidden and row_id != ".hidden" and ".hidden" in categories:
            return False

        if row_id != "all" and row_id not in categories:
            return False

    return True
