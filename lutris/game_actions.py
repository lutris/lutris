"""Handle game specific actions"""
import os
from gi.repository import GLib
from lutris.command import MonitoredCommand
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.util import open_uri
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.config.edit_game import EditGameConfigDialog
from lutris.gui.installerwindow import InstallerWindow
from lutris.gui.uninstallgamedialog import UninstallGameDialog
from lutris.util.system import path_exists
from lutris.util.log import logger
from lutris.util import xdgshortcuts
from lutris.util import resources


class GameActions:
    """Regroup a list of callbacks for a game"""
    def __init__(self, application, window):
        self.application = application
        self.window = window
        self.game_id = None
        self._game = None

    @staticmethod
    def get_hidden_entries(game):
        """Return a dictionary of actions that should be hidden for a game"""
        return {
            "add": game.is_installed,
            "install": game.is_installed,
            "install_more": not game.is_installed,
            "play": not game.is_installed,
            "configure": not game.is_installed,
            "desktop-shortcut": (
                not game.is_installed or xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "menu-shortcut": (
                not game.is_installed or xdgshortcuts.menu_launcher_exists(game.slug, game.id)
            ),
            "rm-desktop-shortcut": (
                not game.is_installed
                or not xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "rm-menu-shortcut": (
                not game.is_installed
                or not xdgshortcuts.menu_launcher_exists(game.slug, game.id)
            ),
            "browse": not game.is_installed or game.runner_name == "browser",
        }

    @staticmethod
    def get_disabled_entries(game):
        """Return a dictionary of actions that should be disabled for a game"""
        return {
            "execute-script": game.runner and not game.runner.system_config.get("manual_command")
        }

    @property
    def game(self):
        if not self.game_id:
            raise RuntimeError("The Game ID has not been set")
        if not self._game:
            self._game = Game(self.game_id)
        return self._game

    def get_game_actions(self):
        """Return a list of game actions and their callbacks"""
        return [
            (
                "play", "Play",
                self.on_game_run
            ),
            (
                "install", "Install",
                self.on_install_clicked
            ),
            (
                "add", "Add manually",
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

    def on_game_run(self, *_args):
        """Launch a game"""
        self.application.launch(self.game_id)

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
            self.window.view.set_installed(game)
            GLib.idle_add(resources.fetch_icon, game.slug, self.window.on_image_downloaded)
            self.window.sidebar_listbox.update()

        AddGameDialog(
            self,
            game=self.game,
            runner=self.game.runner_name,
            callback=lambda: on_game_added(self.game),
        )

    def on_edit_game_configuration(self, _widget):
        """Edit game preferences"""

        def on_dialog_saved():
            game_id = dialog.game.id
            self.window.view.remove_game(game_id)
            self.window.view.add_game_by_id(game_id)
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
        if path and os.path.exists(path):
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
