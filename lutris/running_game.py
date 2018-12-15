from gi.repository import Gtk
from lutris.util.log import logger
from lutris.game import Game
from lutris.gui.installerwindow import InstallerWindow
from lutris.gui.logdialog import LogDialog

class RunningGameBox(Gtk.Box):
    def __init__(self, game):
        super().__init__(self, spacing=6, homogeneous=False)
        label = Gtk.Label("%s is running" % game.name)
        self.pack_start(label, True, True, 0)
        self.stop_button = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic", Gtk.IconSize.MENU)
        self.pack_start(self.stop_button, False, False, 0)
        self.log_button = Gtk.Button.new_from_icon_name("utilities-terminal-symbolic", Gtk.IconSize.MENU)
        self.pack_start(self.log_button, False, False, 0)
        self.show_all()

class RunningGame:
    """Class for manipulating running games"""
    def __init__(self, game_id, application=None, window=None):
        self.application = application
        self.window = window
        self.game_id = game_id
        self.running_game_box = None
        self.game = Game(game_id)
        self.game.connect("game-error", self.window.on_game_error)
        self.game.connect("game-stop", self.on_stop)

    def play(self):
        if self.game.is_installed:
            self.game.play()
        else:
            logger.warning("%s is not available", self.game.slug)
            InstallerWindow(
                game_slug=self.game.slug, parent=self.window, application=self.application
            )
        self.running_game_box = RunningGameBox(self.game)
        self.running_game_box.stop_button.connect("clicked", self.on_stop)
        self.running_game_box.log_button.connect("clicked", self.on_show_logs)
        self.window.add_running_game(self.running_game_box)

    def on_stop(self, widget):
        """Stops the game"""
        self.game.stop()
        self.running_game_box.destroy()
        self.application.running_games.pop(self.application.running_games.index(self))
        self.window.remove_running_game()

    def on_show_logs(self, _widget):
        """Display game log in a LogDialog"""
        log_title = u"Log for {}".format(self.game)
        log_window = LogDialog(
            title=log_title, buffer=self.game.log_buffer, parent=self.window
        )
        log_window.run()
        log_window.destroy()
