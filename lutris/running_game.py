from gi.repository import Gtk
from lutris.game import Game


class RunningGameBox(Gtk.Box):
    def __init__(self, game):
        super().__init__(self, spacing=6, homogeneous=False)
        self.show_all()


class RunningGame:
    """Class for manipulating running games"""
    def __init__(self, game_id, application=None, window=None):
        self.application = application
        self.window = window
        self.game_id = game_id
        self.running_game_box = None
        self.game = Game(game_id)
