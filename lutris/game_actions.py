"""Handle game specific actions"""
import os
import signal
from gi.repository import Gio
from lutris.command import MonitoredCommand
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.util import open_uri
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.config.edit_game import EditGameConfigDialog
from lutris.gui.installerwindow import InstallerWindow
from lutris.gui.uninstallgamedialog import UninstallGameDialog
from lutris.gui.logdialog import LogDialog
from lutris.util.system import path_exists
from lutris.util.log import logger
from lutris.util import xdgshortcuts


class GameActions:
    """Regroup a list of callbacks for a game"""
    def __init__(self, application=None, window=None):
        self.application = application or Gio.Application.get_default()
        self.window = window
        self.game_id = None
        self._game = None

    @property
    def game(self):
        if not self._game:
            self._game = self.application.get_game_by_id(self.game_id)
            if not self._game:
                self._game = Game(self.game_id)
            self._game.connect("game-error", self.window.on_game_error)
            self._game.connect("game-stop", self.on_stop)
        return self._game

    @property
    def is_game_running(self):
        return bool(self.application.get_game_by_id(self.game_id))

    def set_game(self, game=None, game_id=None):
        if game:
            self._game = game
            self.game_id = game.id
        else:
            self._game = None
            self.game_id = game_id

    def get_game_actions(self):
        """Return a list of game actions and their callbacks"""
        return [
            (
                "play", "Play",
                self.on_game_run
            ),
            (
                "stop", "Stop",
                self.on_stop
            ),
            (
                "show_logs", "Show logs",
                self.on_show_logs
            ),
            (
                "install", "Install",
                self.on_install_clicked
            ),
            (
                "add", "Add installed game",
                self.on_add_manually
            ),
            (
                "configure", "Configure",
                self.on_edit_game_configuration
            ),
            (
                "execute-script", "Execute script",
                self.on_execute_script_clicked
            ),
            (
                "browse", "Browse files",
                self.on_browse_files
            ),
            (
                "desktop-shortcut", "Create desktop shortcut",
                self.on_create_desktop_shortcut,
            ),
            (
                "rm-desktop-shortcut", "Delete desktop shortcut",
                self.on_remove_desktop_shortcut,
            ),
            (
                "menu-shortcut", "Create application menu shortcut",
                self.on_create_menu_shortcut,
            ),
            (
                "rm-menu-shortcut", "Delete application menu shortcut",
                self.on_remove_menu_shortcut,
            ),
            (
                "install_more", "Install another version",
                self.on_install_clicked
            ),
            (
                "remove", "Remove",
                self.on_remove_game
            ),
            (
                "view", "View on Lutris.net",
                self.on_view_game
            ),
        ]

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""
        return {
            "add": not self.game.is_installed,
            "install": not self.game.is_installed,
            "play": self.game.is_installed and not self.is_game_running,
            "stop": self.is_game_running,
            "show_logs": self.game.is_installed,
            "configure": bool(self.game.is_installed),
            "install_more": self.game.is_installed,
            "execute-script": bool(
                self.game.is_installed
                and self.game.runner.system_config.get("manual_command")
            ),
            "desktop-shortcut": (
                self.game.is_installed
                and not xdgshortcuts.desktop_launcher_exists(self.game.slug, self.game.id)
            ),
            "menu-shortcut": (
                self.game.is_installed
                and not xdgshortcuts.menu_launcher_exists(self.game.slug, self.game.id)
            ),
            "rm-desktop-shortcut": bool(
                self.game.is_installed
                and xdgshortcuts.desktop_launcher_exists(self.game.slug, self.game.id)
            ),
            "rm-menu-shortcut": bool(
                self.game.is_installed
                and xdgshortcuts.menu_launcher_exists(self.game.slug, self.game.id)
            ),
            "browse": self.game.is_installed and self.game.runner_name != "browser",
            "remove": self.game.is_installed,
            "view": True
        }

    def get_disabled_entries(self):
        """Return a dictionary of actions that should be disabled for a game"""
        return {
            "show_logs": not self.is_game_running,
        }

    def on_game_run(self, *_args):
        """Launch a game"""
        self.application.launch(self.game)

    def on_stop(self, caller):
        """Stops the game"""
        try:
            game = self.application.running_games.pop(
                self.application.running_games.index(self.game)
            )
        except ValueError:
            logger.warning("%s not in running game list", self.game_id)
            return

        try:
            os.kill(game.game_thread.game_process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        logger.debug("Removed game with ID %s from running games", self.game_id)

    def on_show_logs(self, _widget):
        """Display game log in a LogDialog"""
        log_title = u"Log for {}".format(self.game)
        log_window = LogDialog(
            title=log_title, buffer=self.game.log_buffer, parent=self.window
        )
        log_window.run()
        log_window.destroy()

    def on_install_clicked(self, *_args):
        """Install a game"""
        # Install the currently selected game in the UI
        return InstallerWindow(
            parent=self.window,
            game_slug=self.game.slug,
            application=self.application,
        )

    def on_add_manually(self, _widget, *_args):
        """Callback that presents the Add game dialog"""

        def on_game_added(game):
            self.window.game_store.update(game)
            self.window.sidebar_listbox.update()

        AddGameDialog(
            self.window,
            game=self.game,
            runner=self.game.runner_name,
            callback=lambda: on_game_added(self.game),
        )

    def on_edit_game_configuration(self, _widget):
        """Edit game preferences"""

        def on_dialog_saved():
            game_id = dialog.game.id
            self.window.game_store.remove_game(game_id)
            self.window.game_store.add_game_by_id(game_id)
            self.window.view.set_selected_game(game_id)
            self.window.sidebar_listbox.update()

        dialog = EditGameConfigDialog(self.window, self.game, on_dialog_saved)

    def on_execute_script_clicked(self, _widget):
        """Execute the game's associated script"""
        manual_command = self.game.runner.system_config.get("manual_command")
        if path_exists(manual_command):
            MonitoredCommand(
                [manual_command],
                include_processes=[os.path.basename(manual_command)],
                cwd=self.game.directory,
            ).start()
            logger.info("Running %s in the background", manual_command)

    def on_browse_files(self, _widget):
        """Callback to open a game folder in the file browser"""
        path = self.game.get_browse_dir()
        if not path:
            dialogs.NoticeDialog("This game has no installation directory")
        elif path_exists(path):
            open_uri("file://%s" % path)
        else:
            dialogs.NoticeDialog("Can't open %s \nThe folder doesn't exist." % path)

    def on_create_menu_shortcut(self, *_args):
        """Add the selected game to the system's Games menu."""
        xdgshortcuts.create_launcher(self.game.slug, self.game.id, self.game.name, menu=True)

    def on_create_desktop_shortcut(self, *_args):
        """Create a desktop launcher for the selected game."""
        xdgshortcuts.create_launcher(self.game.slug, self.game.id, self.game.name, desktop=True)

    def on_remove_menu_shortcut(self, *_args):
        """Remove an XDG menu shortcut"""
        xdgshortcuts.remove_launcher(self.game.slug, self.game.id, menu=True)

    def on_remove_desktop_shortcut(self, *_args):
        """Remove a .desktop shortcut"""
        xdgshortcuts.remove_launcher(self.game.slug, self.game.id, desktop=True)

    def on_view_game(self, _widget):
        """Callback to open a game on lutris.net"""
        open_uri("https://lutris.net/games/%s" % self.game.slug)

    def on_remove_game(self, *_args):
        """Callback that present the uninstall dialog to the user"""
        UninstallGameDialog(
            game_id=self.game.id, callback=self.window.remove_game_from_view, parent=self.window
        )
