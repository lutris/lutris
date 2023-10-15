"""Handle game specific actions"""

# Standard Library
# pylint: disable=too-many-public-methods
import os
from gettext import gettext as _

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
from lutris.gui.dialogs.uninstall_game import RemoveGameDialog, UninstallGameDialog
from lutris.gui.widgets.utils import open_uri
from lutris.services.lutris import download_lutris_media
from lutris.util import xdgshortcuts
from lutris.util.log import logger
from lutris.util.steam import shortcut as steam_shortcut
from lutris.util.strings import gtk_safe, slugify
from lutris.util.system import path_exists
from lutris.util.wine.shader_cache import update_shader_cache


class GameActions:
    """Regroup a list of callbacks for a game"""

    def __init__(self, game, window, application=None):
        self.application = application or Gio.Application.get_default()
        self.window = window  # also used as a LaunchUIDelegate
        self.game = game

    @property
    def is_game_running(self):
        return self.game and self.game.is_db_stored and bool(self.application.get_running_game_by_id(self.game.id))

    @property
    def is_game_removable(self):
        return self.game and (self.game.is_installed or self.game.is_db_stored)

    def on_game_state_changed(self, game):
        """Handler called when the game has changed state"""
        if self.game and game.id == self.game.get_safe_id():
            self.game = game

    def get_game_actions(self):
        """Return a list of game actions and their callbacks"""
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
            ("add", _("Add installed game"), self.on_add_manually),
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
        if steam_shortcut.vdf_file_exists():
            has_steam_shortcut = steam_shortcut.shortcut_exists(self.game)
            is_steam_game = steam_shortcut.is_steam_game(self.game)
        else:
            has_steam_shortcut = False
            is_steam_game = False
        return {
            "add": not self.game.is_installed,
            "duplicate": self.game.is_installed,
            "install": not self.game.is_installed,
            "play": self.game.is_installed and not self.is_game_running,
            "update": self.game.is_updatable,
            "update-shader-cache": self.game.is_cache_managed,
            "install_dlcs": self.game.is_updatable,
            "stop": self.is_game_running,
            "configure": bool(self.game.is_installed),
            "browse": self.game.is_installed and self.game.runner_name != "browser",
            "show_logs": self.game.is_installed,
            "favorite": not self.game.is_favorite and self.game.is_installed,
            "category": self.game.is_installed,
            "deletefavorite": self.game.is_favorite,
            "install_more": not self.game.service and self.game.is_installed,
            "execute-script": bool(
                self.game.is_installed and self.game.runner
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
            "steam-shortcut": (
                self.game.is_installed
                and not has_steam_shortcut
                and not is_steam_game
            ),
            "rm-desktop-shortcut": bool(
                self.game.is_installed
                and xdgshortcuts.desktop_launcher_exists(self.game.slug, self.game.id)
            ),
            "rm-menu-shortcut": bool(
                self.game.is_installed
                and xdgshortcuts.menu_launcher_exists(self.game.slug, self.game.id)
            ),
            "rm-steam-shortcut": bool(
                self.game.is_installed
                and has_steam_shortcut
                and not is_steam_game
            ),
            "remove": self.is_game_removable,
            "view": True,
            "hide": self.game.is_installed and not self.game.is_hidden,
            "unhide": self.game.is_hidden,
        }

    def on_game_launch(self, *_args):
        """Launch a game"""
        self.game.launch(self.window)

    def get_running_game(self):
        if self.game and self.game.is_db_stored:
            ids = self.application.get_running_game_ids()
            for game_id in ids:
                if str(game_id) == str(self.game.id):
                    return self.game
            logger.warning("Game %s not in %s", self.game.id, ids)

        return None

    def on_game_stop(self, *_args):
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
            game=self.game,
            buffer=_buffer,
            application=self.application
        )

    def on_install_clicked(self, *_args):
        """Install a game"""
        # Install the currently selected game in the UI
        if not self.game.slug:
            raise RuntimeError("No game to install: %s" % self.game.get_safe_id())
        self.game.emit("game-install")

    def on_update_clicked(self, _widget):
        self.game.emit("game-install-update")

    def on_install_dlc_clicked(self, _widget):
        self.game.emit("game-install-dlc")

    def on_update_shader_cache(self, _widget):
        update_shader_cache(self.game)

    def on_locate_installed_game(self, _button, game):
        """Show the user a dialog to import an existing install to a DRM free service

        Params:
            game (Game): Game instance without a database ID, populated with a fields the service can provides
        """
        AddGameDialog(self.window, game=game)

    def on_add_manually(self, _widget, *_args):
        """Callback that presents the Add game dialog"""
        return AddGameDialog(self.window, game=self.game, runner=self.game.runner_name)

    def on_game_duplicate(self, _widget):
        duplicate_game_dialog = InputDialog(
            {
                "parent": self.window,
                "question": _(
                    "Do you wish to duplicate %s?\nThe configuration will be duplicated, "
                    "but the games files will <b>not be duplicated</b>.\n"
                    "Please enter the new name for the copy:"
                ) % gtk_safe(self.game.name),
                "title": _("Duplicate game?"),
            }
        )
        result = duplicate_game_dialog.run()
        if result != Gtk.ResponseType.OK:
            duplicate_game_dialog.destroy()
            return
        new_name = duplicate_game_dialog.user_value

        old_config_id = self.game.game_config_id
        if old_config_id:
            new_config_id = duplicate_game_config(self.game.slug, old_config_id)
        else:
            new_config_id = None
        duplicate_game_dialog.destroy()
        db_game = get_game_by_field(self.game.id, "id")
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
        self.application.show_window(EditGameConfigDialog, game=self.game, parent=self.window)

    def on_add_favorite_game(self, _widget):
        """Add to favorite Games list"""
        self.game.add_to_favorites()

    def on_delete_favorite_game(self, _widget):
        """delete from favorites"""
        self.game.remove_from_favorites()

    def on_edit_game_categories(self, _widget):
        """Edit game categories"""
        self.application.show_window(EditGameCategoriesDialog, game=self.game, parent=self.window)

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
            dialogs.NoticeDialog(_("This game has no installation directory"))
        elif path_exists(path):
            open_uri("file://%s" % path)
        else:
            dialogs.NoticeDialog(_("Can't open %s \nThe folder doesn't exist.") % path)

    def on_create_menu_shortcut(self, *_args):
        """Add the selected game to the system's Games menu."""
        launch_config_name = self._select_game_launch_config_name(self.game)
        if launch_config_name is not None:
            xdgshortcuts.create_launcher(self.game.slug, self.game.id, self.game.name, menu=True)

    def on_create_steam_shortcut(self, *_args):
        """Add the selected game to steam as a nonsteam-game."""
        launch_config_name = self._select_game_launch_config_name(self.game)
        if launch_config_name is not None:
            steam_shortcut.create_shortcut(self.game, launch_config_name)

    def on_create_desktop_shortcut(self, *_args):
        """Create a desktop launcher for the selected game."""
        launch_config_name = self._select_game_launch_config_name(self.game)
        if launch_config_name is not None:
            xdgshortcuts.create_launcher(self.game.slug, self.game.id, self.game.name, launch_config_name, desktop=True)

    def on_remove_menu_shortcut(self, *_args):
        """Remove an XDG menu shortcut"""
        xdgshortcuts.remove_launcher(self.game.slug, self.game.id, menu=True)

    def on_remove_steam_shortcut(self, *_args):
        """Remove the selected game from list of non-steam apps."""
        steam_shortcut.remove_shortcut(self.game)

    def on_remove_desktop_shortcut(self, *_args):
        """Remove a .desktop shortcut"""
        xdgshortcuts.remove_launcher(self.game.slug, self.game.id, desktop=True)

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

    def on_view_game(self, _widget):
        """Callback to open a game on lutris.net"""
        open_uri("https://lutris.net/games/%s" % self.game.slug.replace("_", "-"))

    def on_remove_game(self, *_args):
        """Callback that present the uninstall dialog to the user"""
        if self.game.is_installed:
            UninstallGameDialog(game_id=self.game.id, parent=self.window).run()
        else:
            RemoveGameDialog(game_id=self.game.id, parent=self.window).run()
