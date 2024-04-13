"""Module that actually runs the games."""

from __future__ import annotations

import json
import os
import shutil
from gettext import gettext as _
from typing import cast

from gi.repository import Gio, GObject

from lutris import settings
from lutris.config import LutrisConfig
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import sql
from lutris.exceptions import GameConfigError, InvalidGameMoveError
from lutris.game_launcher import GameLauncher
from lutris.installer import InstallationKind
from lutris.runner_interpreter import export_bash_script
from lutris.runners import import_runner, is_valid_runner_name
from lutris.runners.runner import Runner
from lutris.util import extract, jobs, strings, system, xdgshortcuts
from lutris.util.log import LOG_BUFFERS, logger
from lutris.util.steam.shortcut import remove_shortcut as remove_steam_shortcut
from lutris.util.system import fix_path_case
from lutris.util.yaml import write_yaml_to_file


class Game(GObject.Object):
    """This class takes cares of loading the configuration for a game
    and running it.
    """

    PRIMARY_LAUNCH_CONFIG_NAME = "(primary)"
    __gsignals__ = {
        "game-updated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game_id: str = None):
        super().__init__()
        self._id = str(game_id) if game_id else None  # pylint: disable=invalid-name

        # Load attributes from database
        game_data = games_db.get_game_by_field(game_id, "id")

        self.slug: str = game_data.get("slug") or ""
        self._runner_name: str = game_data.get("runner") or ""
        self.directory: str = game_data.get("directory") or ""
        self.name: str = game_data.get("name") or ""
        self.sortname: str = game_data.get("sortname") or ""
        self.game_config_id: str = game_data.get("configpath") or ""
        self.is_installed: bool = bool(game_data.get("installed") and self.game_config_id)
        self.platform: str = game_data.get("platform") or ""
        self.year: str = game_data.get("year") or ""
        self.lastplayed: int = game_data.get("lastplayed") or 0
        self.custom_images = set()
        if game_data.get("has_custom_banner"):
            self.custom_images.add("banner")
        if game_data.get("has_custom_icon"):
            self.custom_images.add("icon")
        if game_data.get("has_custom_coverart_big"):
            self.custom_images.add("coverart_big")
        self.service = game_data.get("service")
        self.appid = game_data.get("service_id")
        self.playtime: float = float(game_data.get("playtime") or 0.0)
        self.discord_id = game_data.get("discord_id")  # Discord App ID for RPC

        self._config: LutrisConfig = None
        self._runner = None
        self.game_launcher = GameLauncher(self)

    @staticmethod
    def create_empty_service_game(db_game, service) -> Game:
        """Creates a Game from the database data from ServiceGameCollection, which is
        not a real game, but which can be used to install. Such a game has no ID, but
        has an 'appid' and slug."""
        game = Game()
        game.name = db_game["name"]
        game.slug = service.get_installed_slug(db_game)
        game.runner_name = service.get_installed_runner_name(db_game)

        if "service_id" in db_game:
            game.appid = db_game["service_id"]
        elif service:
            game.appid = db_game["appid"]

        game.service = service.id if service else None
        return game

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        value = self.name or "Game (no name)"
        if self.runner_name:
            value += " (%s)" % self.runner_name
        return value

    @property
    def id(self) -> str:
        if not self._id:
            logger.error("The game '%s' has no ID, it is not stored in the database.", self.name)
        return cast(str, self._id)

    @property
    def is_db_stored(self) -> bool:
        """True if this Game has an ID, which means it is saved in the database."""
        return bool(self._id)

    @property
    def is_updatable(self):
        """Return whether the game can be upgraded"""
        return self.is_installed and self.service in ["gog", "itchio"]

    def get_categories(self):
        """Return the categories the game is in."""
        return categories_db.get_categories_in_game(self.id) if self.is_db_stored else []

    def update_game_categories(self, added_category_names, removed_category_names):
        """add to / remove from categories"""
        for added_category_name in added_category_names:
            self.add_category(added_category_name, no_signal=True)

        for removed_category_name in removed_category_names:
            self.remove_category(removed_category_name, no_signal=True)

        self.emit("game-updated")

    def add_category(self, category_name, no_signal=False):
        """add game to category"""
        if not self.is_db_stored:
            raise RuntimeError("Games that do not have IDs cannot belong to categories.")

        category = categories_db.get_category(category_name)
        if category is None:
            category_id = categories_db.add_category(category_name)
        else:
            category_id = category["id"]
        categories_db.add_game_to_category(self.id, category_id)

        if not no_signal:
            self.emit("game-updated")

    def remove_category(self, category_name, no_signal=False):
        """remove game from category"""
        if not self.is_db_stored:
            return

        category = categories_db.get_category(category_name)
        if category is None:
            return
        category_id = category["id"]
        categories_db.remove_category_from_game(self.id, category_id)

        if not no_signal:
            self.emit("game-updated")

    @property
    def is_favorite(self) -> bool:
        """Return whether the game is in the user's favorites"""
        return "favorite" in self.get_categories()

    def mark_as_favorite(self, is_favorite: bool) -> None:
        """Place the game in the favorite's category, or remove it.
        This change is applied at once, and does not need to be saved."""
        if self.is_favorite != bool(is_favorite):
            if is_favorite:
                self.add_category("favorite")
            else:
                self.remove_category("favorite")

    @property
    def is_hidden(self) -> bool:
        """Return whether the game is in the user's favorites"""
        return ".hidden" in self.get_categories()

    def mark_as_hidden(self, is_hidden: bool) -> None:
        """Place the game in the hidden category, or remove it.
        This change is applied at once, and does not need to be saved."""
        if self.is_hidden != bool(is_hidden):
            if is_hidden:
                self.add_category(".hidden")
            else:
                self.remove_category(".hidden")

    @property
    def formatted_playtime(self) -> str:
        """Return a human-readable formatted play time"""
        return strings.get_formatted_playtime(self.playtime)

    def get_browse_dir(self) -> str:
        """Return the path to open with the Browse Files action."""
        return self.resolve_game_path()

    def resolve_game_path(self) -> str:
        """Return the game's directory; if it is not known this will try to find
        it. This can still return an empty string if it can't do that."""
        if self.directory:
            return os.path.expanduser(self.directory)  # expanduser just in case!
        if self.has_runner:
            return self.runner.resolve_game_path()
        return ""

    @property
    def config(self) -> LutrisConfig:
        if not self.is_installed or not self.game_config_id:
            raise ValueError("Tried to access config of uninstalled")
        if not self._config:
            self._config = LutrisConfig(runner_slug=self.runner_name, game_config_id=self.game_config_id)
        return self._config

    @config.setter
    def config(self, value):
        self._config = value
        self._runner = None
        if value:
            self.game_config_id = value.game_config_id

    def reload_config(self):
        """Triggers the config to reload when next used; this also reloads the runner,
        so that it will pick up the new configuration."""
        self._config = None
        self._runner = None

    @property
    def runner_name(self) -> str:
        return self._runner_name

    @runner_name.setter
    def runner_name(self, value: str) -> None:
        self._runner_name = value or ""
        if self._runner and self._runner.name != value:
            self._runner = None

    @property
    def has_runner(self) -> bool:
        return bool(self._runner_name and is_valid_runner_name(self._runner_name))

    @property
    def runner(self) -> Runner:
        if not self.has_runner:
            raise GameConfigError(_("Invalid game configuration: Missing runner"))

        if not self._runner:
            runner_class = import_runner(self.runner_name)
            self._runner = runner_class(self.config)
        return cast(Runner, self._runner)

    @runner.setter
    def runner(self, value: Runner) -> None:
        self._runner = value
        if value:
            self._runner_name = value.name

    def install(self, launch_ui_delegate) -> None:
        """Request installation of a game"""
        if not self.slug:
            raise ValueError("Invalid game passed: %s" % self)

        if not self.service or self.service == "lutris":
            application = Gio.Application.get_default()
            application.show_lutris_installer_window(game_slug=self.slug)
            return

        service = launch_ui_delegate.get_service(self.service)
        db_game = service.get_service_db_game(self)
        if not db_game:
            logger.error("Can't find %s for %s", self.name, service.name)
            return

        try:
            game_id = service.install(db_game)
        except ValueError as e:
            logger.debug(e)
            game_id = None

        if game_id:

            def on_error(_game, error):
                logger.exception("Unable to install game: %s", error)
                return True

            game = Game(game_id)
            game.game_launcher.connect("game-error", on_error)
            game.game_launcher.launch(launch_ui_delegate)

    def install_updates(self, install_ui_delegate):
        service = install_ui_delegate.get_service(self.service)
        db_game = games_db.get_game_by_field(self.id, "id")

        def on_installers_ready(installers, error):
            if error:
                raise error  # bounce errors off the backstop

            if not installers:
                raise RuntimeError(_("No updates found"))

            application = Gio.Application.get_default()
            application.show_installer_window(
                installers, service, self.appid, installation_kind=InstallationKind.UPDATE
            )

        jobs.AsyncCall(service.get_update_installers, on_installers_ready, db_game)
        return True

    def install_dlc(self, install_ui_delegate):
        service = install_ui_delegate.get_service(self.service)
        db_game = games_db.get_game_by_field(self.id, "id")

        def on_installers_ready(installers, error):
            if error:
                raise error  # bounce errors off the backstop

            if not installers:
                raise RuntimeError(_("No DLC found"))

            application = Gio.Application.get_default()
            application.show_installer_window(installers, service, self.appid, installation_kind=InstallationKind.DLC)

        jobs.AsyncCall(service.get_dlc_installers_runner, on_installers_ready, db_game, db_game["runner"])
        return True

    def uninstall(self, delete_files: bool = False) -> None:
        """Uninstall a game, but do not remove it from the library.

        Params:
            delete_files (bool): Delete the game files
        """
        sql.db_update(settings.DB_PATH, "games", {"installed": 0, "runner": ""}, {"id": self.id})
        if self.config:
            self.config.remove()
        xdgshortcuts.remove_launcher(self.slug, self.id, desktop=True, menu=True)
        remove_steam_shortcut(self)
        if delete_files and self.has_runner:
            # self.directory here, not self.resolve_game_path; no guessing at
            # directories when we delete them
            self.runner.remove_game_data(app_id=self.appid, game_path=self.directory)
        self.is_installed = False
        self._config = None
        self._runner = None

        if self.id in LOG_BUFFERS:  # Reset game logs on removal
            log_buffer = LOG_BUFFERS[self.id]
            log_buffer.delete(log_buffer.get_start_iter(), log_buffer.get_end_iter())

    def delete(self) -> None:
        """Delete a game from the library; must be uninstalled first."""
        if self.is_installed:
            raise RuntimeError(_("Uninstall the game before deleting"))
        games_db.delete_game(self.id)
        self._id = None

    def set_platform_from_runner(self) -> None:
        """Set the game's platform from the runner"""
        if not self.has_runner:
            logger.warning("Game has no runner, can't set platform")
            return
        self.platform = self.runner.get_platform()
        if not self.platform:
            logger.warning("The %s runner didn't provide a platform for %s", self.runner.human_name, self)

    def save(self, no_signal=False) -> None:
        """
        Save the game's config and metadata.
        """
        if self.config:
            configpath = self.config.game_config_id
            logger.debug("Saving %s with config ID %s", self, self.config.game_config_id)
            self.config.save()
        else:
            logger.warning("Saving %s with the configuration missing", self)
            configpath = ""
        self.set_platform_from_runner()

        game_data = {
            "name": self.name,
            "sortname": self.sortname,
            "runner": self.runner_name,
            "slug": self.slug,
            "platform": self.platform,
            "directory": self.directory,
            "installed": self.is_installed,
            "year": self.year,
            "lastplayed": self.lastplayed,
            "configpath": configpath,
            "id": self.id,
            "playtime": self.playtime,
            "service": self.service,
            "service_id": self.appid,
            "discord_id": self.discord_id,
            "has_custom_banner": "banner" in self.custom_images,
            "has_custom_icon": "icon" in self.custom_images,
            "has_custom_coverart_big": "coverart_big" in self.custom_images,
        }
        self._id = str(games_db.add_or_update(**game_data))
        if not no_signal:
            self.emit("game-updated")

    def save_platform(self) -> None:
        """Save only the platform field- do not restore any other values the user may have changed
        in another window."""
        games_db.update_existing(id=self.id, slug=self.slug, platform=self.platform)
        self.emit("game-updated")

    def save_lastplayed(self) -> None:
        """Save only the lastplayed field- do not restore any other values the user may have changed
        in another window."""
        games_db.update_existing(id=self.id, slug=self.slug, lastplayed=self.lastplayed, playtime=self.playtime)
        self.emit("game-updated")

    def get_path_from_config(self) -> str:
        """Return the path of the main entry point for a game"""
        if not self.config:
            logger.warning("%s has no configuration", self)
            return ""
        game_config = self.config.game_config

        # Skip MAME roms referenced by their ID
        if self.runner_name == "mame":
            if "main_file" in game_config and "." not in game_config["main_file"]:
                return ""

        for key in ["exe", "main_file", "iso", "rom", "disk-a", "path", "files"]:
            if key in game_config:
                path = game_config[key]
                if key == "files":
                    path = path[0]

                if path:
                    path = os.path.expanduser(path)
                    if not path.startswith("/"):
                        path = os.path.join(self.directory, path)

                    # The Wine runner fixes case mismatches automatically,
                    # sort of like Windows, so we need to do the same.
                    if self.runner_name == "wine":
                        path = fix_path_case(path)

                    return path

        logger.warning("No path found in %s", self.config)
        return ""

    def get_store_name(self) -> str:
        store = self.service
        if not store:
            return ""
        if self.service == "humblebundle":
            return "humble"
        return store

    def write_script(self, script_path, launch_ui_delegate) -> None:
        """Output the launch argument in a bash script"""
        gameplay_info = self.game_launcher.get_gameplay_info(launch_ui_delegate)
        if not gameplay_info:
            # User cancelled; errors are raised as exceptions instead of this
            return
        export_bash_script(self.runner, gameplay_info, script_path)

    def move(self, new_location, no_signal=False) -> str:
        logger.info("Moving %s to %s", self, new_location)
        new_config = ""
        old_location = self.directory
        target_directory = self._get_move_target_directory(new_location)

        if new_location.startswith(old_location):
            raise InvalidGameMoveError(
                _("Lutris can't move '%s' to a location inside of itself, '%s'.") % (old_location, new_location)
            )

        self.directory = target_directory
        self.save(no_signal=no_signal)

        with open(self.config.game_config_path, encoding="utf-8") as config_file:
            for line in config_file.readlines():
                if target_directory in line:
                    new_config += line
                else:
                    new_config += line.replace(old_location, target_directory)
        with open(self.config.game_config_path, "w", encoding="utf-8") as config_file:
            config_file.write(new_config)

        if not system.path_exists(old_location):
            logger.warning("Initial location %s does not exist, files may have already been moved.")
            return target_directory

        try:
            shutil.move(old_location, new_location)
        except OSError as ex:
            logger.error(
                "Failed to move %s to %s, you may have to move files manually (Exception: %s)",
                old_location,
                new_location,
                ex,
            )
        return target_directory

    def set_location(self, new_location) -> str:
        target_directory = self._get_move_target_directory(new_location)
        self.directory = target_directory
        self.save()
        return target_directory

    def _get_move_target_directory(self, new_location) -> str:
        old_location = self.directory
        if old_location and os.path.exists(old_location):
            game_directory = os.path.basename(old_location)
            return os.path.join(new_location, game_directory)

        return new_location


def export_game(slug, dest_dir) -> None:
    """Export a full game folder along with some lutris metadata"""
    # List of runner where we know for sure that 1 folder = 1 game.
    # For runners that handle ROMs, we have to handle this more finely.
    # There is likely more than one game in a ROM folder but a ROM
    # might have several files (like a bin/cue, or a multi-disk game)
    exportable_runners = [
        "linux",
        "wine",
        "dosbox",
        "scummvm",
    ]
    db_game = games_db.get_game_by_field(slug, "slug")
    if not db_game:
        logger.error("Game %s not found", slug)
        return
    if db_game["runner"] not in exportable_runners:
        raise RuntimeError("Game %s can't be exported." % db_game["name"])
    if not db_game["directory"]:
        raise RuntimeError("No game directory set. Could we guess it?")

    game = Game(db_game["id"])
    db_game["config"] = game.config.game_level
    game_path = db_game["directory"]
    config_path = os.path.join(db_game["directory"], "%s.lutris" % slug)
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(db_game, config_file, indent=2)
    archive_path = os.path.join(dest_dir, "%s.tar.xz" % slug)
    command = ["tar", "cJf", archive_path, os.path.basename(game_path)]
    system.execute(command, cwd=os.path.dirname(game_path))
    logger.info("%s exported to %s", slug, archive_path)


def import_game(file_path, dest_dir) -> None:
    """Import a game in Lutris"""
    if not os.path.exists(file_path):
        raise RuntimeError("No file %s" % file_path)
    logger.info("Importing %s to %s", file_path, dest_dir)
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    original_file_list = set(os.listdir(dest_dir))
    extract.extract_archive(file_path, dest_dir, merge_single=False)
    new_file_list = set(os.listdir(dest_dir))
    new_dir = list(new_file_list - original_file_list)[0]
    game_dir = os.path.join(dest_dir, new_dir)
    try:
        game_config = [f for f in os.listdir(game_dir) if f.endswith(".lutris")][0]
    except IndexError:
        logger.error("No Lutris configuration file found in archive")
        return

    with open(os.path.join(game_dir, game_config), encoding="utf-8") as config_file:
        lutris_config = json.load(config_file)
    old_dir = lutris_config["directory"]
    with open(os.path.join(game_dir, game_config), "r", encoding="utf-8") as config_file:
        config_data = config_file.read()
    config_data = config_data.replace(old_dir, game_dir)
    with open(os.path.join(game_dir, game_config), "w", encoding="utf-8") as config_file:
        config_file.write(config_data)
    with open(os.path.join(game_dir, game_config), encoding="utf-8") as config_file:
        lutris_config = json.load(config_file)
    config_filename = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % lutris_config["configpath"])
    write_yaml_to_file(lutris_config["config"], config_filename)
    game_id = games_db.add_game(
        name=lutris_config["name"],
        runner=lutris_config["runner"],
        slug=lutris_config["slug"],
        platform=lutris_config["platform"],
        directory=game_dir,
        installed=lutris_config["installed"],
        year=lutris_config["year"],
        lastplayed=lutris_config["lastplayed"],
        configpath=lutris_config["configpath"],
        playtime=lutris_config["playtime"],
        service=lutris_config["service"],
        service_id=lutris_config["service_id"],
    )
    print("Added game with ID %s" % game_id)
