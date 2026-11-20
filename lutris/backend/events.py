"""The events frontends follow, about the games in the library. Each carries plain
data, as the backend's calls return, so it can be sent to another process later.

Handlers run on the main loop, after the event, as with any NotificationSource.
These re-announce the core's own notifications (lutris.game), which carry live
Game objects.
"""

from typing import Any

from lutris import game as core
from lutris.backend.games import game_info_from
from lutris.database.categories import CATEGORIES_UPDATED
from lutris.database.saved_searches import SAVED_SEARCHES_UPDATED
from lutris.util.notifications import NotificationSource

# Fired with a GameInfo when a game's details change: its name, playtime, categories...
GAME_CHANGED = NotificationSource()
# Fired with a GameInfo when a game has been installed
GAME_INSTALLED = NotificationSource()
# Fired with a GameInfo when a game's launch begins; GAME_STARTED or GAME_STOPPED follows,
# whether the game starts or the launch is cancelled or fails
GAME_LAUNCHING = NotificationSource()
# Fired with a GameInfo when a game's process has started
GAME_STARTED = NotificationSource()
# Fired with a GameInfo when a game has stopped, or its launch ended without starting it
GAME_STOPPED = NotificationSource()
# Fired with a game's id and what its launch is doing (such as downloading a runtime),
# to show while it launches; an empty status when that's over
GAME_LAUNCH_STATUS = NotificationSource()
# Fired with a game's id and the error, when a game fails and nothing else reported it
GAME_FAILED = NotificationSource()
# Fired with nothing when categories are added, renamed or removed, or games change category
CATEGORIES_CHANGED = NotificationSource()
# Fired with nothing when saved searches are added, changed or removed
SAVED_SEARCHES_CHANGED = NotificationSource()


def _forward_game(event: NotificationSource) -> Any:
    def forward(game: core.Game) -> None:
        event.fire(game_info_from(game))

    return forward


core.GAME_UPDATED.register(_forward_game(GAME_CHANGED))
core.GAME_INSTALLED.register(_forward_game(GAME_INSTALLED))
core.GAME_START.register(_forward_game(GAME_LAUNCHING))
core.GAME_STARTED.register(_forward_game(GAME_STARTED))
core.GAME_STOPPED.register(_forward_game(GAME_STOPPED))
core.GAME_LAUNCH_STATUS.register(lambda game: GAME_LAUNCH_STATUS.fire(game.id, game.launch_status))
core.GAME_UNHANDLED_ERROR.register(lambda game, error: GAME_FAILED.fire(game.id, error))
CATEGORIES_UPDATED.register(lambda *_args: CATEGORIES_CHANGED.fire())
SAVED_SEARCHES_UPDATED.register(lambda *_args: SAVED_SEARCHES_CHANGED.fire())
