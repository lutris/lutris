"""Sorting of the games displayed in a view.

The view settings that drive the sort (which field to sort on, in which direction, and whether
installed games come first) are read by the window and handed to the functions here, which are
all pure, so they can be tested without a window.
"""

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any, TypeVar

from lutris.gui.views import (
    COL_INSTALLED_AT,
    COL_INSTALLED_AT_TEXT,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_NAME,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT,
    COL_SORTNAME,
    COL_YEAR,
)
from lutris.util.strings import get_natural_sort_key

ItemType = TypeVar("ItemType")

# Values used when a game has no value for the sort that is in use.
SORT_DEFAULTS: dict[str, Any] = {
    "name": "",
    "year": 0,
    "lastplayed": 0.0,
    "installed_at": 0.0,
    "playtime": 0.0,
}

# The columns of the game store that carry the values a sort uses; if any of these change for
# a game, the view has to be sorted again.
SORT_SENSITIVE_COLUMNS: dict[str, set[int]] = {
    "name": {COL_NAME, COL_SORTNAME},
    "year": {COL_YEAR},
    "lastplayed": {COL_LASTPLAYED, COL_LASTPLAYED_TEXT},
    "installed_at": {COL_INSTALLED_AT, COL_INSTALLED_AT_TEXT},
    "playtime": {COL_PLAYTIME, COL_PLAYTIME_TEXT},
}


def normalize_view_sorting(setting: str | None) -> str:
    """Returns the sort that the given 'view_sorting' setting names, defaulting to 'name'.

    Settings saved by older versions may end in '_text' (the name of a text column), which we
    strip, and may name a sort that no longer exists, which the callers tolerate as a blank."""
    value = setting or "name"
    if value.endswith("_text"):
        value = value[:-5]
    return value


def get_sort_sensitive_columns(view_sorting: str) -> set[int]:
    """Returns the columns of the game store that affect the sort order when the view is
    sorted by 'view_sorting'; this is empty for a sort that no column carries.

    Users may have obsolete view_sorting settings, so we must tolerate those as well; they
    get no sensitive columns either."""
    return SORT_SENSITIVE_COLUMNS.get(view_sorting, set())


def convert_sort_value(value: Any, view_sorting: str) -> Any:
    """Converts 'value' to the type required for the sort that is in use. Returns None if this
    can't be managed."""
    try:
        if not value:
            return None
        if view_sorting == "name":
            return str(value)
        if view_sorting == "year":
            # Years can take many forms! We'll try to convert as best we can.
            if isinstance(value, datetime):
                return int(value.year)
            else:
                try:
                    return int(value)
                except ValueError:
                    as_date = datetime.strptime(str(value), "%Y-%m-%d")
                    return int(as_date.year)
        else:
            return float(value)
    except ValueError:
        return None  # unable to parse value?


def extend_sort_value(value: Any, view_sorting: str, view_reverse_order: bool) -> Any:
    """Expands the value to sort by to a more complex form, for smarter sorting."""
    if view_sorting == "name":
        return get_natural_sort_key(value)
    if view_sorting == "year":
        contains_year = bool(value)
        if view_reverse_order:
            contains_year = not contains_year
        return contains_year, value
    return value


def apply_view_sort(
    items: Iterable[ItemType],
    view_sorting: str,
    view_reverse_order: bool = False,
    view_sorting_installed_first: bool = True,
    service: Any = None,
    resolver: Callable[[ItemType], Any] | None = None,
) -> list[ItemType]:
    """This sorts a list of items according to the view settings given; the items can be
    anything, but you can provide a resolver that provides a database game dictionary for
    each one; this dictionary carries the data we sort on (though any field may be missing).

    This sort always sorts installed games ahead of uninstalled ones, even when
    the sort is set to descending.

    This treats 'name' sorting specially, applying a natural sort so that
    'Mega slap battler 20' comes after 'Mega slap battler 3'."""

    def get_sort_default(item: ItemType) -> Any:
        """Returns the default value to use when the value is missing; we may be able
        to extract this from the item."""
        if view_sorting == "year" and service:
            service_year = convert_sort_value(service.get_game_release_date(item), view_sorting)
            if service_year:
                return service_year

        # Users may have obsolete view_sorting settings, so
        # we must tolerate them. We treat them all as blank.
        return SORT_DEFAULTS.get(view_sorting, "")

    def get_sort_value(item: ItemType) -> Any:
        db_game: Any = resolver(item) if resolver else item
        if not db_game:
            installation_flag = False
            value = None
        else:
            installation_flag = bool(db_game.get("installed"))

            # When sorting by name, check for a valid sortname first, then fall back
            # on name if valid sortname is not available.
            if view_sorting == "name":
                value = db_game.get("sortname") or db_game.get("name")
            else:
                value = db_game.get(view_sorting)

        value = convert_sort_value(value, view_sorting) or get_sort_default(item)
        value = extend_sort_value(value, view_sorting, view_reverse_order)

        if view_sorting_installed_first:
            # We want installed games to always be first, even in
            # a descending sort.
            if view_reverse_order:
                installation_flag = not installation_flag
            if view_sorting == "name":
                installation_flag = not installation_flag
            return installation_flag, value
        return value

    reverse = view_reverse_order if view_sorting == "name" else not view_reverse_order
    return sorted(items, key=get_sort_value, reverse=reverse)
