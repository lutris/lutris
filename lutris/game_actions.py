"""Handle game specific actions"""

# Standard Library
# pylint: disable=too-many-public-methods
import os
from gettext import gettext as _
from typing import List

from gi.repository import Gio, Gtk

from lutris.command import MonitoredCommand
from lutris.config import duplicate_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.gui.config.edit_game import EditGameConfigDialog
from lutris.gui.config.edit_game_categories import EditGameCategoriesDialog
from lutris.gui.dialogs import InputDialog
from lutris.gui.dialogs.log import LogWindow
from lutris.gui.dialogs.uninstall_game import UninstallMultipleGamesDialog
from lutris.gui.widgets.utils import open_uri
from lutris.services.lutris import download_lutris_media
from lutris.util import xdgshortcuts
from lutris.util.log import logger
from lutris.util.steam import shortcut as steam_shortcut
from lutris.util.strings import gtk_safe, slugify
from lutris.util.system import path_exists
from lutris.util.wine.shader_cache import update_shader_cache


class BaseGameActions:
    def __init__(self, games, window, application=None):
        self.application = application or Gio.Application.get_default()
        self.window = window  # also used as a LaunchUIDelegate
        self.games = games

    def get_game_actions(self):
        """Return a list of game actions and their callbacks"""
        return []

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""
        return {}

    @property
    def is_game_launchable(self):
        return False

    async def on_game_launch(self, *_args):
        """Launch a game"""

    @property
    def is_game_running(self):
        return False

    def on_game_stop(self, *_args):
        """Stops the game"""

    @property
    def is_installable(self):
        for game in self.games:
            if not game.is_installed:
                return True

        return False

    def on_install_clicked(self, *_args):
        """Install a game"""
        # Install the currently selected game in the UI
        for game in self.games:
            if not game.is_installed:
                if not game.slug:
                    game_id = game.id if game.is_db_stored else game.name
                    raise RuntimeError("No game to install: %s" % game_id)
                game.emit("game-install")

    def on_locate_installed_game(self, *_args):
        """Show the user a dialog to import an existing install to a DRM free service

        Params:
            games ([Game]): List of Game instances without a database ID, populated with fields the service can provides
        """
        for game in self.games:
            AddGameDialog(self.window, game=game, runner=game.runner_name)

    @property
    def is_game_removable(self):
        for game in self.games:
            if game.is_installed or game.is_db_stored:
                return True

        return False

    def on_remove_game(self, *_args):
        """Callback that present the uninstall dialog to the user"""
        game_ids = [g.id for g in self.games if g.is_installed or g.is_db_stored]
        application = Gio.Application.get_default()
        dlg = application.show_window(UninstallMultipleGamesDialog, parent=self.window)
        dlg.add_games(game_ids)

    def on_view_game(self, _widget):
        """Callback to open a game on lutris.net"""
        for game in self.games:
            open_uri("https://lutris.net/games/%s" % game.slug.replace("_", "-"))


class GameActions(BaseGameActions):
    """Regroup a list of callbacks for a game"""

    @property
    def is_game_launchable(self):
        for game in self.games:
            if game.is_installed and not self.is_game_running:
                return True

        return False

    @property
    def is_game_running(self):
        for game in self.games:
            if game.is_db_stored and self.application.is_game_running_by_id(game.id):
                return True
        return False

    def get_game_actions(self):
        if not self.games:
            return []

        if len(self.games) > 1:
            return [
                ("stop", _("Stop"), self.on_game_stop),
                (None, "-", None),
                ("favorite", _("Add to favorites"), self.on_add_favorite_game),
                ("deletefavorite", _("Remove from favorites"), self.on_delete_favorite_game),
                ("hide", _("Hide game from library"), self.on_hide_game),
                ("unhide", _("Unhide game from library"), self.on_unhide_game),
                (None, "-", None),
                ("remove", _("Remove"), self.on_remove_game),
            ]

        return [
            ("play", _("Play"), self.on_game_launch),
            ("stop", _("Stop"), self.on_game_stop),
            ("execute-script", _("Execute script"), self.on_execute_script_clicked),
            ("show_logs", _("Show logs"), self.on_show_logs),
            (None, "-", None),
            ("configure", _("Configure"), self.on_edit_game_configuration),
            ("category", _("Categories"), self.on_edit_game_categories),
            ("browse", _("Browse files"), self.on_browse_files),
            ("favorite", _("Add to favorites"), self.on_add_favorite_game),
            ("deletefavorite", _("Remove from favorites"), self.on_delete_favorite_game),
            ("hide", _("Hide game from library"), self.on_hide_game),
            ("unhide", _("Unhide game from library"), self.on_unhide_game),
            ("update-shader-cache", _("Update shader cache"), self.on_update_shader_cache),
            (None, "-", None),
            ("install", _("Install"), self.on_install_clicked),
            ("install_more", _("Install another version"), self.on_install_clicked),
            ("install_dlcs", "Install DLCs", self.on_install_dlc_clicked),
            ("update", _("Install updates"), self.on_update_clicked),
            ("desktop-shortcut", _("Create desktop shortcut"), self.on_create_desktop_shortcut),
            ("rm-desktop-shortcut", _("Delete desktop shortcut"), self.on_remove_desktop_shortcut),
            ("menu-shortcut", _("Create application menu shortcut"), self.on_create_menu_shortcut),
            ("rm-menu-shortcut", _("Delete application menu shortcut"), self.on_remove_menu_shortcut),
            ("steam-shortcut", _("Create steam shortcut"), self.on_create_steam_shortcut),
            ("rm-steam-shortcut", _("Delete steam shortcut"), self.on_remove_steam_shortcut),
            ("view", _("View on Lutris.net"), self.on_view_game),
            ("duplicate", _("Duplicate"), self.on_game_duplicate),
            (None, "-", None),
            ("remove", _("Remove"), self.on_remove_game),
        ]

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""
        if not self.games:
            return {}

        if len(self.games) > 1:
            return {
                "stop": self.is_game_running,
                "favorite": any(g for g in self.games if not g.is_favorite),
                "deletefavorite": any(g for g in self.games if g.is_favorite),
                "hide": any(g for g in self.games if g.is_installed and not g.is_hidden),
                "unhide": any(g for g in self.games if g.is_hidden),
                "remove": self.is_game_removable,
            }

        game = self.games[0]
        if steam_shortcut.vdf_file_exists():
            has_steam_shortcut = steam_shortcut.shortcut_exists(game)
            is_steam_game = steam_shortcut.is_steam_game(game)
        else:
            has_steam_shortcut = False
            is_steam_game = False
        return {
            "duplicate": game.is_installed,
            "install": self.is_installable,
            "play": self.is_game_launchable,
            "update": game.is_updatable,
            "update-shader-cache": game.is_cache_managed,
            "install_dlcs": game.is_updatable,
            "stop": self.is_game_running,
            "configure": bool(game.is_installed),
            "browse": game.is_installed and game.runner_name != "browser",
            "show_logs": game.is_installed,
            "category": True,
            "favorite": not game.is_favorite,
            "deletefavorite": game.is_favorite,
            "install_more": not game.service and game.is_installed,
            "execute-script": bool(
                game.is_installed and game.has_runner
                and game.runner.system_config.get("manual_command")
            ),
            "desktop-shortcut": (
                game.is_installed
                and not xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "menu-shortcut": (
                game.is_installed
                and not xdgshortcuts.menu_launcher_exists(game.slug, game.id)
            ),
            "steam-shortcut": (
                game.is_installed
                and not has_steam_shortcut
                and not is_steam_game
            ),
            "rm-desktop-shortcut": bool(
                game.is_installed
                and xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "rm-menu-shortcut": bool(
                game.is_installed
                and xdgshortcuts.menu_launcher_exists(game.slug, game.id)
            ),
            "rm-steam-shortcut": bool(
                game.is_installed
                and has_steam_shortcut
                and not is_steam_game
            ),
            "remove": self.is_game_removable,
            "view": True,
            "hide": game.is_installed and not game.is_hidden,
            "unhide": game.is_hidden,
        }

    async def on_game_launch(self, *_args):
        """Launch a game"""
        for game in self.games:
            if game.is_installed and game.is_db_stored:
                if not self.application.is_game_running_by_id(game.id):
                    await game.launch(self.window)

    def get_running_games(self):
        running_games = []
        for game in self.games:
            if game and game.is_db_stored:
                ids = self.application.get_running_game_ids()
                for game_id in ids:
                    if str(game_id) == game.id:
                        running_games.append(game)
        return running_games

    def on_game_stop(self, *_args):
        """Stops the game"""
        games = self.get_running_games()
        for game in games:
            game.force_stop()

    def on_show_logs(self, _widget):
        """Display game log"""
        for game in self.games:
            _buffer = game.log_buffer
            if not _buffer:
                logger.info("No log for game %s", game)
            return LogWindow(
                game=game,
                buffer=_buffer,
                application=self.application
            )

    def on_update_clicked(self, _widget):
        for game in self.games:
            game.emit("game-install-update")

    def on_install_dlc_clicked(self, _widget):
        for game in self.games:
            game.emit("game-install-dlc")

    def on_update_shader_cache(self, _widget):
        for game in self.games:
            update_shader_cache(game)

    def on_game_duplicate(self, _widget):
        for game in self.games:
            base_name = game.name.strip().rstrip("0123456789").rstrip()
            if not base_name:
                base_name = game.name

            for num in range(2, 999):
                initial_name = f"{base_name} {num}".strip()

                if not get_game_by_field(initial_name, "name"):
                    break

            duplicate_game_dialog = InputDialog(
                {
                    "parent": self.window,
                    "question": _(
                        "Do you wish to duplicate %s?\nThe configuration will be duplicated, "
                        "but the games files will <b>not be duplicated</b>.\n"
                        "Please enter the new name for the copy:"
                    ) % gtk_safe(game.name),
                    "title": _("Duplicate game?"),
                    "initial_value": initial_name
                }
            )
            result = duplicate_game_dialog.run()
            if result != Gtk.ResponseType.OK:
                duplicate_game_dialog.destroy()
                return
            new_name = duplicate_game_dialog.user_value

            old_config_id = game.game_config_id
            if old_config_id:
                new_config_id = duplicate_game_config(game.slug, old_config_id)
            else:
                new_config_id = None
            duplicate_game_dialog.destroy()
            db_game = get_game_by_field(game.id, "id")
            db_game["name"] = new_name
            db_game["slug"] = slugify(new_name)
            db_game["lastplayed"] = None
            db_game["playtime"] = 0.0
            db_game["configpath"] = new_config_id
            db_game.pop("id")
            # Disconnect duplicate from service- there should be at most
            # 1 PGA game for a service game.
            db_game.pop("service", None)
            db_game.pop("service_id", None)

            game_id = add_game(**db_game)
            download_lutris_media(db_game["slug"])
            new_game = Game(game_id)
            new_game.save()

    def on_edit_game_configuration(self, _widget):
        """Edit game preferences"""
        for game in self.games:
            self.application.show_window(EditGameConfigDialog, game=game, parent=self.window)

    def on_add_favorite_game(self, _widget):
        """Add to favorite Games list"""
        for game in self.games:
            if not game.is_favorite:
                game.add_to_favorites()

    def on_delete_favorite_game(self, _widget):
        """delete from favorites"""
        for game in self.games:
            if game.is_favorite:
                game.remove_from_favorites()

    def on_edit_game_categories(self, _widget):
        """Edit game categories"""
        for game in self.games:
            self.application.show_window(EditGameCategoriesDialog, game=game, parent=self.window)

    def on_hide_game(self, _widget):
        """Add a game to the list of hidden games"""
        for game in self.games:
            if not game.is_hidden:
                game.set_hidden(True)

    def on_unhide_game(self, _widget):
        """Removes a game from the list of hidden games"""
        for game in self.games:
            if game.is_hidden:
                game.set_hidden(False)

    def on_execute_script_clicked(self, _widget):
        """Execute the game's associated script"""
        for game in self.games:
            manual_command = game.runner.system_config.get("manual_command")
            if path_exists(manual_command):
                MonitoredCommand(
                    [manual_command],
                    include_processes=[os.path.basename(manual_command)],
                    cwd=game.directory,
                ).start()
                logger.info("Running %s in the background", manual_command)

    def on_browse_files(self, _widget):
        """Callback to open a game folder in the file browser"""
        for game in self.games:
            path = game.get_browse_dir()
            if not path:
                dialogs.NoticeDialog(_("This game has no installation directory"))
            elif path_exists(path):
                open_uri("file://%s" % path)
            else:
                dialogs.NoticeDialog(_("Can't open %s \nThe folder doesn't exist.") % path)

    def on_create_menu_shortcut(self, *_args):
        """Add the selected game to the system's Games menu."""
        for game in self.games:
            launch_config_name = self._select_game_launch_config_name(game)
            if launch_config_name is not None:
                xdgshortcuts.create_launcher(game.slug, game.id, game.name, menu=True)

    def on_create_steam_shortcut(self, *_args):
        """Add the selected game to steam as a nonsteam-game."""
        for game in self.games:
            launch_config_name = self._select_game_launch_config_name(game)
            if launch_config_name is not None:
                steam_shortcut.create_shortcut(game, launch_config_name)

    def on_create_desktop_shortcut(self, *_args):
        """Create a desktop launcher for the selected game."""
        for game in self.games:
            launch_config_name = self._select_game_launch_config_name(game)
            if launch_config_name is not None:
                xdgshortcuts.create_launcher(game.slug, game.id, game.name, launch_config_name, desktop=True)

    def on_remove_menu_shortcut(self, *_args):
        """Remove an XDG menu shortcut"""
        for game in self.games:
            xdgshortcuts.remove_launcher(game.slug, game.id, menu=True)

    def on_remove_steam_shortcut(self, *_args):
        """Remove the selected game from list of non-steam apps."""
        for game in self.games:
            steam_shortcut.remove_shortcut(game)

    def on_remove_desktop_shortcut(self, *_args):
        """Remove a .desktop shortcut"""
        for game in self.games:
            xdgshortcuts.remove_launcher(game.slug, game.id, desktop=True)

    def _select_game_launch_config_name(self, game):
        game_config = game.config.game_level.get("game", {})
        configs = game_config.get("launch_configs")

        if not configs:
            return ""  # use primary configuration

        dlg = dialogs.LaunchConfigSelectDialog(game, configs, title=_("Select shortcut target"), parent=self.window)
        if not dlg.confirmed:
            return None  # no error here- the user cancelled out

        config_index = dlg.config_index
        return configs[config_index - 1]["name"] if config_index > 0 else ""


class ServiceGameActions(BaseGameActions):
    """Regroup a list of callbacks for a service game"""

    def get_game_actions(self):
        return [
            ("install", _("Install"), self.on_install_clicked),
            ("add", _("Locate installed game"), self.on_locate_installed_game),
            ("view", _("View on Lutris.net"), self.on_view_game),
        ]

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""
        return {
            "install": self.is_installable,
            "add": self.is_installable,
            "view": True
        }


def get_game_actions(games: List[Game], window, application=None) -> BaseGameActions:
    if games:
        if len(games) == 1:
            game = games[0]
            if game.is_db_stored:
                return GameActions(games, window, application)

            if game.service:
                return ServiceGameActions(games, window, application)
        else:
            return GameActions(games, window)

    # If given no games, or the games are not of a kind we can handle,
    # the base class acts as an empty set of actions.
    return BaseGameActions(games, window, application)
