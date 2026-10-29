"""Rules for the games a view keeps selected across a rebuild.

When a view's game store is replaced, the rows it shows are rebuilt from scratch; the selection
the user had is only meaningful if the games it pointed at are still present. This module holds
that rule as a pure function, so it can be exercised without a window.
"""

from collections.abc import Callable, Iterable
from typing import Any

GameId = Any


def retained_game_ids(selected_ids: Iterable[GameId], is_available: Callable[[GameId], bool]) -> list[GameId]:
    """Returns the selected game ids that are still available, in their original order and
    without duplicates.

    'is_available' reports whether a game id can still be found after the rebuild. Ids that
    have been filtered out, hidden or removed are dropped, so a rebuilt view never keeps a
    selection pointing at a game it no longer shows. A missing id (None) is always dropped.
    """
    seen: set[GameId] = set()
    retained: list[GameId] = []
    for game_id in selected_ids:
        if game_id is None or game_id in seen:
            continue
        if is_available(game_id):
            retained.append(game_id)
            seen.add(game_id)
    return retained
