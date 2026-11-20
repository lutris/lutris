"""Turns errors in a game's operations into a stopped game and an error notification"""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.game import Game

AnyCallable = Callable[..., Any]


def watch_game_errors(game_stop_result: Any, game: "Game | None" = None) -> Callable[[AnyCallable], AnyCallable]:
    """Decorator used to catch exceptions and send events instead of propagating them normally.
    If 'game_stop_result' is not None, and the decorated function returns that, this will
    send game-stop and make the game stopped as well. This simplifies handling cancellation.
    Also, if an error occurs and is emitted, the function returns this value, so callers
    can tell that the function failed.

    If you do not provide a game object directly, it is assumed to be in the first argument to
    the decorated method (which is 'self', typically).
    """
    captured_game = game

    def inner_decorator(function: AnyCallable) -> AnyCallable:
        @wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Catch all exceptions and emit an event."""
            game = captured_game if captured_game else args[0]

            try:
                result = function(*args, **kwargs)
                if game_stop_result is not None and result == game_stop_result and game.state != game.STATE_STOPPED:
                    game.stop_game()
                return result
            except Exception as ex:
                logger.exception("%s has encountered an error: %s", game, ex, exc_info=ex)
                if game.state != game.STATE_STOPPED:
                    game.stop_game()
                game.signal_error(ex)
                return game_stop_result

        return cast(AnyCallable, wrapper)

    return inner_decorator
