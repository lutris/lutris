from lutris.util.log import logger
from lutris.game import Game
from lutris.gui.installerwindow import InstallerWindow


class RunningGame:
    """Class for manipulating running games"""
    def __init__(self, game_id, application=None, window=None):
        self.application = application
        self.window = window
        self.game_id = game_id
        self.game = Game(game_id)
        self.game.connect("game-error", self.window.on_game_error)
        self.start_time = None
        self.stop_time = None

    def play(self):
        if self.game.is_installed:
            self.game.play()
        else:
            logger.warning("%s is not available", self.game.slug)
            InstallerWindow(
                game_slug=self.game.slug, parent=self.window, application=self.application
            )
        self.game.play()