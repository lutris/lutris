"""Handle game specific actions"""

# Standard Library
# pylint: disable=too-many-public-methods
import os
from gettext import gettext as _
from typing import List

from gi.repository import Gio, Gtk

from lutris.config import duplicate_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.gui.config.edit_game import EditGameConfigDialog
from lutris.gui.config.edit_game_categories import EditGameCategoriesDialog
from lutris.gui.dialogs import InputDialog
from lutris.gui.dialogs.log import LogWindow
from lutris.gui.dialogs.uninstall_dialog import UninstallDialog
from lutris.gui.widgets.utils import open_uri
from lutris.monitored_command import MonitoredCommand
from lutris.services.lutris import download_lutris_media
from lutris.util import xdgshortcuts
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.steam import shortcut as steam_shortcut
from lutris.util.strings import gtk_safe, slugify
from lutris.util.system import path_exists


class GameActions:
    """These classes provide a set of action to apply to a game or list of games, and can be used
    to populate menus. The base class handles the no-games case, for which there are no actions. But
    it also includes the code for actions that are shared between the subclasses. It also has methods for
    actions that are invokes externally by the GameBar."""

    def __init__(self, window: Gtk.Window, application=None):
        self.application = application or Gio.Application.get_default()
        self.window = window  # also used as a LaunchUIDelegate and InstallUIDelegate

    def get_games(self):
        """Return the list of games that the actions apply to."""
        return []

    def get_game_actions(self):
        """Return a list of game actions and their callbacks, Each item is a tuple
        of two strs and a callable, the action ID, it's human-readable name, and
        a callback to invoke to perform it. Menu separators are represented hre
        as (None, "-", None).
        """
        return []

    def get_displayed_entries(self):
        """Return a dictionary of flags indicating which actions are visible; the keys
        are the action ids from get_game_actions(), and the values are booleans indicating
        the action's visibility."""
        return {}

    @property
    def is_game_launchable(self):
        for game in self.get_games():
            if game.is_installed and not self.is_game_running:
                return True

        return False

    def on_game_launch(self, *_args):
        """Launch a game"""

    @property
    def is_game_running(self):
        for game in self.get_games():
            if game.is_db_stored and self.application.is_game_running_by_id(game.id):
                return True
        return False

    def on_game_stop(self, *_args):
        """Stops the game"""
        games = self.get_running_games()
        for game in games:
            game.force_stop()

    def get_running_games(self):
        running_games = []
        for game in self.get_games():
            if game and game.is_db_stored:
                ids = self.application.get_running_game_ids()
                for game_id in ids:
                    if str(game_id) == game.id:
                        running_games.append(game)
        return running_games

    @property
    def is_installable(self):
        for game in self.get_games():
            if not game.is_installed:
                return True

        return False

    def on_install_clicked(self, *_args):
        """Install a game"""
        # Install the currently selected game in the UI
        for game in self.get_games():
            if not game.slug:
                game_id = game.id if game.is_db_stored else game.name
                raise RuntimeError("No game to install: %s" % game_id)
            game.install(launch_ui_delegate=self.window)

    def on_add_favorite_game(self, _widget):
        """Add to favorite Games list"""
        for game in self.get_games():
            game.mark_as_favorite(True)

    def on_delete_favorite_game(self, _widget):
        """delete from favorites"""
        for game in self.get_games():
            game.mark_as_favorite(False)

    def on_hide_game(self, _widget):
        """Add a game to the list of hidden games"""
        for game in self.get_games():
            game.mark_as_hidden(True)

    def on_unhide_game(self, _widget):
        """Removes a game from the list of hidden games"""
        for game in self.get_games():
            game.mark_as_hidden(False)

    def on_locate_installed_game(self, *_args):
        """Show the user a dialog to import an existing install to a DRM free service

        Params:
            games ([Game]): List of Game instances without a database ID, populated with fields the service can provides
        """
        for game in self.get_games():
            AddGameDialog(self.window, game=game, runner=game.runner_name)

    def on_view_game(self, _widget):
        """Callback to open a game on lutris.net"""
        for game in self.get_games():
            open_uri("https://lutris.net/games/%s" % game.slug.replace("_", "-"))

    @property
    def is_game_removable(self):
        for game in self.get_games():
            if game.is_installed or game.is_db_stored:
                return True

        return False

    def on_remove_game(self, *_args):
        """Callback that present the uninstall dialog to the user"""
        game_ids = [g.id for g in self.get_games() if g.is_installed or g.is_db_stored]
        application = Gio.Application.get_default()
        dlg = application.show_window(UninstallDialog, parent=self.window)
        dlg.add_games(game_ids)

    def on_edit_game_categories(self, _widget):
        """Edit game categories"""
        games = self.get_games()
        if len(games) == 1:
            # Individual games get individual separate windows
            self.application.show_window(EditGameCategoriesDialog, game=games[0], parent=self.window)
        else:

            def add_games(window):
                window.add_games(self.get_games())

            # Multi-select means a common categories window for all of them; we can wind
            # up adding games to it if it's already open
            self.application.show_window(EditGameCategoriesDialog, update_function=add_games, parent=self.window)


class MultiGameActions(GameActions):
    """This actions class handles actions on multiple games together, and only iof they
    are 'db stored' games, not service games. This supports a subset of the actions
    of SingleGameActions."""

    def __init__(self, games: List[Game], window: Gtk.Window, application=None):
        super().__init__(window, application)
        self.games = games

    def get_games(self):
        return self.games

    def get_game_actions(self):
        return [
            ("stop", _("Stop"), self.on_game_stop),
            (None, "-", None),
            ("category", _("Categories"), self.on_edit_game_categories),
            ("favorite", _("Add to favorites"), self.on_add_favorite_game),
            ("deletefavorite", _("Remove from favorites"), self.on_delete_favorite_game),
            ("hide", _("Hide game from library"), self.on_hide_game),
            ("unhide", _("Unhide game from library"), self.on_unhide_game),
            (None, "-", None),
            ("remove", _("Remove"), self.on_remove_game),
        ]

    def get_displayed_entries(self):
        return {
            "stop": self.is_game_running,
            "category": True,
            "favorite": any(g for g in self.games if not g.is_favorite),
            "deletefavorite": any(g for g in self.games if g.is_favorite),
            "hide": any(g for g in self.games if g.is_installed and not g.is_hidden),
            "unhide": any(g for g in self.games if g.is_hidden),
            "remove": self.is_game_removable,
        }


class SingleGameActions(GameActions):
    """This actions class handles actions on a single game, which is a 'db stored' game,
    not a service game. This provides the largest selection of actions, including many
    that are unique to it."""

    def __init__(self, game: Game, window: Gtk.Window, application=None):
        super().__init__(window, application)
        self.game = game

    def get_games(self):
        return [self.game]

    def get_game_actions(self):
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
            (None, "-", None),
            ("install", _("Install"), self.on_install_clicked),
            ("install_more", _("Install another version"), self.on_install_clicked),
            ("install_dlcs", _("Install DLCs"), self.on_install_dlc_clicked),
            ("update", _("Install updates"), self.on_update_clicked),
            ("add", _("Locate installed game"), self.on_locate_installed_game),
            ("desktop-shortcut", _("Create desktop shortcut"), self.on_create_desktop_shortcut),
            ("rm-desktop-shortcut", _("Delete desktop shortcut"), self.on_remove_desktop_shortcut),
            ("menu-shortcut", _("Create application menu shortcut"), self.on_create_menu_shortcut),
            ("rm-menu-shortcut", _("Delete application menu shortcut"), self.on_remove_menu_shortcut),
            ("steam-shortcut", _("Create Steam shortcut"), self.on_create_steam_shortcut),
            ("rm-steam-shortcut", _("Delete Steam shortcut"), self.on_remove_steam_shortcut),
            ("view", _("View on Lutris.net"), self.on_view_game),
            ("duplicate", _("Duplicate"), self.on_game_duplicate),
            (None, "-", None),
            ("remove", _("Remove"), self.on_remove_game),
        ]

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""

        game = self.game
        has_steam = steam_shortcut.vdf_file_exists()
        if has_steam:
            has_steam_shortcut = steam_shortcut.shortcut_exists(game)
            is_steam_game = steam_shortcut.is_steam_game(game)
        else:
            has_steam_shortcut = False
            is_steam_game = False

        return {
            "duplicate": game.is_installed,
            "install": self.is_installable,
            "add": not game.is_installed,
            "play": self.is_game_launchable,
            "update": game.is_updatable,
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
                game.is_installed and game.has_runner and game.runner.system_config.get("manual_command")
            ),
            "desktop-shortcut": bool(
                game.is_installed and not xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "menu-shortcut": bool(game.is_installed and not xdgshortcuts.menu_launcher_exists(game.slug, game.id)),
            "steam-shortcut": bool(has_steam and game.is_installed and not has_steam_shortcut and not is_steam_game),
            "rm-desktop-shortcut": bool(game.is_installed and xdgshortcuts.desktop_launcher_exists(game.slug, game.id)),
            "rm-menu-shortcut": bool(game.is_installed and xdgshortcuts.menu_launcher_exists(game.slug, game.id)),
            "rm-steam-shortcut": bool(game.is_installed and has_steam_shortcut and not is_steam_game),
            "remove": self.is_game_removable,
            "view": True,
            "hide": game.is_installed and not game.is_hidden,
            "unhide": game.is_hidden,
        }

    def on_game_launch(self, *_args):
        """Launch a game"""
        game = self.game
        if game.is_installed and game.is_db_stored:
            if not self.application.is_game_running_by_id(game.id):
                game.launch(launch_ui_delegate=self.window)

    def on_execute_script_clicked(self, _widget):
        """Execute the game's associated script"""
        game = self.game
        manual_command = game.runner.system_config.get("manual_command")
        if path_exists(manual_command):
            runner = game.runner
            env = runner.get_env()
            MonitoredCommand(
                [manual_command], include_processes=[os.path.basename(manual_command)], cwd=game.directory, env=env
            ).start()
            logger.info("Running %s in the background", manual_command)

    def on_show_logs(self, _widget):
        """Display game log"""
        game = self.game
        _buffer = game.log_buffer
        if not _buffer:
            logger.info("No log for game %s", game)
        return LogWindow(game=game, buffer=_buffer, application=self.application)

    def on_edit_game_configuration(self, _widget):
        """Edit game preferences"""
        self.application.show_window(EditGameConfigDialog, game=self.game, parent=self.window)

    def on_browse_files(self, _widget):
        """Callback to open a game folder in the file browser"""
        path = self.game.get_browse_dir()
        if not path:
            dialogs.NoticeDialog(_("This game has no installation directory"))
        elif path_exists(path):
            open_uri("file://%s" % path)
        else:
            dialogs.NoticeDialog(_("Can't open %s \nThe folder doesn't exist.") % path)

    def on_install_dlc_clicked(self, _widget):
        self.game.install_dlc(install_ui_delegate=self.window)

    def on_update_clicked(self, _widget):
        self.game.install_updates(install_ui_delegate=self.window)

    def on_create_menu_shortcut(self, *_args):
        """Add the selected game to the system's Games menu."""
        game = self.game
        launch_config_name = self._select_game_launch_config_name(game)
        if launch_config_name is not None:
            xdgshortcuts.create_launcher(game.slug, game.id, game.name, launch_config_name, menu=True)

    def on_create_steam_shortcut(self, *_args):
        """Add the selected game to steam as a nonsteam-game."""
        game = self.game
        launch_config_name = self._select_game_launch_config_name(game)
        if launch_config_name is not None:
            steam_shortcut.create_shortcut(game, launch_config_name)

    def on_create_desktop_shortcut(self, *_args):
        """Create a desktop launcher for the selected game."""
        game = self.game
        launch_config_name = self._select_game_launch_config_name(game)
        if launch_config_name is not None:
            xdgshortcuts.create_launcher(game.slug, game.id, game.name, launch_config_name, desktop=True)

    def on_remove_menu_shortcut(self, *_args):
        """Remove an XDG menu shortcut"""
        game = self.game
        xdgshortcuts.remove_launcher(game.slug, game.id, menu=True)

    def on_remove_steam_shortcut(self, *_args):
        """Remove the selected game from list of non-steam apps."""
        steam_shortcut.remove_shortcut(self.game)

    def on_remove_desktop_shortcut(self, *_args):
        """Remove a .desktop shortcut"""
        game = self.game
        xdgshortcuts.remove_launcher(game.slug, game.id, desktop=True)

    def on_game_duplicate(self, _widget):
        game = self.game

        duplicate_game_dialog = InputDialog(
            {
                "parent": self.window,
                "question": _(
                    "Do you wish to duplicate %s?\nThe configuration will be duplicated, "
                    "but the games files will <b>not be duplicated</b>.\n"
                    "Please enter the new name for the copy:"
                )
                % gtk_safe(game.name),
                "title": _("Duplicate game?"),
                "initial_value": game.name,
            }
        )
        result = duplicate_game_dialog.run()
        if result != Gtk.ResponseType.OK:
            duplicate_game_dialog.destroy()
            return
        new_name = duplicate_game_dialog.user_value

        old_config_id = game.game_config_id
        if old_config_id:
            new_config_id = duplicate_game_config(slugify(new_name), old_config_id)
        else:
            new_config_id = None
        categories = game.get_categories()

        duplicate_game_dialog.destroy()
        db_game = get_game_by_field(game.id, "id")
        db_game["name"] = new_name
        db_game["slug"] = slugify(new_name) if new_name != game.name else game.slug
        db_game["lastplayed"] = None
        db_game["playtime"] = 0.0
        db_game["configpath"] = new_config_id
        db_game.pop("id")
        # Disconnect duplicate from service- there should be at most 1 database game for a service game.
        db_game.pop("service", None)
        db_game.pop("service_id", None)

        game_id = add_game(**db_game)

        new_game = Game(game_id)

        # add categories before the save, so it can emit the signal. add_game()
        # means the game is already on the database, so this is legit.
        for cat in categories:
            new_game.add_category(cat, no_signal=True)

        new_game.save()

        # Download in the background; we'll update the LutrisWindow when this
        # completes, no need to wait for it.
        AsyncCall(download_lutris_media, None, db_game["slug"])

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


class ServiceGameActions(GameActions):
    """This actions class supports a single service game, which has an idiosyncratic set of
    actions."""

    def __init__(self, game: Game, window: Gtk.Window, application=None):
        super().__init__(window, application)
        self.game = game

    def get_games(self):
        return [self.game]

    def get_game_actions(self):
        return [
            ("install", _("Install"), self.on_install_clicked),
            ("add", _("Locate installed game"), self.on_locate_installed_game),
            ("view", _("View on Lutris.net"), self.on_view_game),
        ]

    def get_displayed_entries(self):
        """Return a dictionary of actions that should be shown for a game"""
        return {"install": self.is_installable, "add": self.is_installable, "view": True}


def get_game_actions(games: List[Game], window: Gtk.Window, application=None) -> GameActions:
    """Creates a GameActions instance (which may be a subclass) for the list of games given. If
    it can't figure out a suitable class, it falls back to the base GameActions class, which
    provides no actions."""
    if games:
        if len(games) == 1:
            game = games[0]
            if game.is_db_stored:
                return SingleGameActions(game, window, application)

            if game.service:
                return ServiceGameActions(game, window, application)
        elif all(g.is_db_stored for g in games):
            return MultiGameActions(games, window)

    # If given no games, or the games are not of a kind we can handle,
    # the base class acts as an empty set of actions.
    return GameActions(window, application)
