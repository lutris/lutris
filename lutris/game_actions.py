"""Handle game specific actions"""

# Standard Library
# pylint: disable=too-many-public-methods
import os
from gettext import gettext as _

from gi.repository import Gio

from lutris.command import MonitoredCommand
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.config.edit_game import EditGameConfigDialog
from lutris.gui.dialogs.log import LogWindow
from lutris.gui.dialogs.uninstall_game import RemoveGameDialog, UninstallGameDialog
from lutris.gui.widgets.utils import open_uri
from lutris.util import xdgshortcuts
from lutris.util.log import logger
from lutris.util.system import path_exists


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
            ("play", _("Play"), self.on_game_launch),
            ("stop", _("Stop"), self.on_game_stop),
            ("show_logs", _("Show logs"), self.on_show_logs),
            ("install", _("Install"), self.on_install_clicked),
            ("add", _("Add installed game"), self.on_add_manually),
            ("configure", _("Configure"), self.on_edit_game_configuration),
            ("favorite", _("Add to favorites"), self.on_add_favorite_game),
            ("deletefavorite", _("Remove from favorites"), self.on_delete_favorite_game),
            ("execute-script", _("Execute script"), self.on_execute_script_clicked),
            ("browse", _("Browse files"), self.on_browse_files),
            (
                "desktop-shortcut",
                _("Create desktop shortcut"),
                self.on_create_desktop_shortcut,
            ),
            (
                "rm-desktop-shortcut",
                _("Delete desktop shortcut"),
                self.on_remove_desktop_shortcut,
            ),
            (
                "menu-shortcut",
                _("Create application menu shortcut"),
                self.on_create_menu_shortcut,
            ),
            (
                "rm-menu-shortcut",
                _("Delete application menu shortcut"),
                self.on_remove_menu_shortcut,
            ),
            ("install_more", _("Install another version"), self.on_install_clicked),
            ("remove", _("Remove"), self.on_remove_game),
            ("view", _("View on Lutris.net"), self.on_view_game),
            ("hide", _("Hide game from library"), self.on_hide_game),
            ("unhide", _("Unhide game from library"), self.on_unhide_game),
        ]

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""
        return {
            "add": not self.game.is_installed,
            "install": not self.game.is_installed,
            "play": self.game.is_installed and not self.is_game_running,
            "stop": self.is_game_running,
            "configure": bool(self.game.is_installed),
            "browse": self.game.is_installed and self.game.runner_name != "browser",
            "show_logs": self.game.is_installed,
            "favorite": not self.game.is_favorite,
            "deletefavorite": self.game.is_favorite,
            "install_more": not self.game.service and self.game.is_installed,
            "execute-script": bool(self.game.is_installed and self.game.runner.system_config.get("manual_command")),
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
            "remove": True,
            "view": True,
            "hide": self.game.is_installed and not self.game.is_hidden,
            "unhide": self.game.is_hidden,
        }

    def on_game_launch(self, *_args):
        """Launch a game"""
        self.game.launch()

    def get_running_game(self):
        ids = self.application.get_running_game_ids()
        for game_id in ids:
            if str(game_id) == str(self.game.id):
                return self.game
        logger.warning("Game %s not in %s", self.game_id, ids)

    def on_game_stop(self, _caller):
        """Stops the game"""
        game = self.get_running_game()
        if game:
            game.force_stop()

    def on_show_logs(self, _widget):
        """Display game log"""
        _buffer = self.game.log_buffer
        if not _buffer:
            logger.info("No log for game %s", self.game)
        return LogWindow(
            title=_("Log for {}").format(self.game),
            buffer=_buffer,
            application=self.application
        )

    def on_install_clicked(self, *_args):
        """Install a game"""
        # Install the currently selected game in the UI
        if not self.game.slug:
            raise RuntimeError("No game to install: %s" % self.game.id)
        self.game.emit("game-install")

    def on_locate_installed_game(self, _button, game):
        """Show the user a dialog to import an existing install to a DRM free service

        Params:
            game (Game): Game instance without a database ID, populated with a fields the service can provides
        """
        AddGameDialog(self.window, game=game).run()

    def on_add_manually(self, _widget, *_args):
        """Callback that presents the Add game dialog"""
        AddGameDialog(self.window, game=self.game, runner=self.game.runner_name).run()

    def on_edit_game_configuration(self, _widget):
        """Edit game preferences"""
        EditGameConfigDialog(self.window, self.game).run()

    def on_add_favorite_game(self, _widget):
        """Add to favorite Games list"""
        self.game.add_to_favorites()

    def on_delete_favorite_game(self, _widget):
        """delete from favorites"""
        self.game.remove_from_favorites()

    def on_hide_game(self, _widget):
        """Add a game to the list of hidden games"""
        self.game.set_hidden(True)

    def on_unhide_game(self, _widget):
        """Removes a game from the list of hidden games"""
        self.game.set_hidden(False)

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
            dialogs.NoticeDialog(_("This game has no installation directory"), parent=self.window)
        elif path_exists(path):
            open_uri("file://%s" % path)
        else:
            dialogs.NoticeDialog(_("Can't open %s \nThe folder doesn't exist.") % path, parent=self.window)

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
        if self.game.is_installed:
            UninstallGameDialog(game_id=self.game.id, parent=self.window).run()
        else:
            RemoveGameDialog(game_id=self.game.id, parent=self.window).run()
