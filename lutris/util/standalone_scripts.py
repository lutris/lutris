import logging
import os
from typing import TYPE_CHECKING

from lutris.game import Game

if TYPE_CHECKING:
    from lutris.database.games import DbGameDict
    from lutris.gui.dialogs.delegates import LaunchUIDelegate


def generate_script(
    logger: logging.Logger, launch_ui_delegate: "LaunchUIDelegate", db_game: "DbGameDict", script_path: str
) -> None:
    """Output a script to a file.
    The script is capable of launching a game without the client
    """

    logger.info(f"Try creating script for '{db_game['name']}'")

    def on_error(error: BaseException) -> None:
        logger.exception("Unable to generate script: %s", error)

    game = Game(db_game["id"])
    game.game_error.register(on_error)
    game.reload_config()
    game.write_script(script_path, launch_ui_delegate)
    absolutePath = os.path.abspath(script_path)
    logger.info(f"Wrote script to: '{absolutePath}'")
