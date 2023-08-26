# pylint: disable=wrong-import-position
# pylint: disable=too-many-lines
#
# Copyright (C) 2009 Mathieu Comandon <mathieucomandon@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import logging
import os
import signal
import sys
import tempfile

from datetime import datetime, timedelta
from gettext import gettext as _

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk, GObject

from lutris.runners import get_runner_names, import_runner, InvalidRunner, RunnerInstallationError
from lutris import settings
from lutris.api import parse_installer_url, get_runners
from lutris.exceptions import watch_errors
from lutris.command import exec_command
from lutris.database import games as games_db
from lutris.game import Game, export_game, import_game
from lutris.installer import get_installers
from lutris.gui.dialogs import ErrorDialog, InstallOrPlayDialog, NoticeDialog, LutrisInitDialog
from lutris.gui.dialogs.issue import IssueReportWindow
from lutris.gui.dialogs.delegates import LaunchUIDelegate, InstallUIDelegate, CommandLineUIDelegate
from lutris.gui.installerwindow import InstallerWindow, InstallationKind
from lutris.gui.widgets.status_icon import LutrisStatusIcon
from lutris.migrations import migrate
from lutris.startup import init_lutris, run_all_checks
from lutris.runtime import RuntimeUpdater
from lutris.style_manager import StyleManager
from lutris.util import datapath, log, system
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_dirs
from lutris.services import get_service
from lutris.database.services import ServiceGameCollection

from .lutriswindow import LutrisWindow


class Application(Gtk.Application):

    def __init__(self):
        super().__init__(
            application_id="net.lutris.Lutris",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            register_session=True,
        )

        GObject.add_emission_hook(Game, "game-launch", self.on_game_launch)
        GObject.add_emission_hook(Game, "game-start", self.on_game_start)
        GObject.add_emission_hook(Game, "game-stop", self.on_game_stop)
        GObject.add_emission_hook(Game, "game-install", self.on_game_install)
        GObject.add_emission_hook(Game, "game-install-update", self.on_game_install_update)
        GObject.add_emission_hook(Game, "game-install-dlc", self.on_game_install_dlc)

        GLib.set_application_name(_("Lutris"))
        self.force_updates = False
        self.css_provider = Gtk.CssProvider.new()
        self.window = None
        self.launch_ui_delegate = LaunchUIDelegate()
        self.install_ui_delegate = InstallUIDelegate()

        self.running_games = Gio.ListStore.new(Game)
        self.app_windows = {}
        self.tray = None

        self.quit_on_game_exit = False
        self.style_manager = None

        if os.geteuid() == 0:
            NoticeDialog(_("Do not run Lutris as root."))
            sys.exit(2)

        try:
            self.css_provider.load_from_path(os.path.join(datapath.get(), "ui", "lutris.css"))
        except GLib.Error as e:
            logger.exception(e)

        if hasattr(self, "add_main_option"):
            self.add_arguments()
        else:
            ErrorDialog(_("Your Linux distribution is too old. Lutris won't function properly."))

    def add_arguments(self):
        if hasattr(self, "set_option_context_summary"):
            self.set_option_context_summary(_(
                "Run a game directly by adding the parameter lutris:rungame/game-identifier.\n"
                "If several games share the same identifier you can use the numerical ID "
                "(displayed when running lutris --list-games) and add "
                "lutris:rungameid/numerical-id.\n"
                "To install a game, add lutris:install/game-identifier."
            ))
        else:
            logger.warning("GLib.set_option_context_summary missing, was added in GLib 2.56 (Released 2018-03-12)")
        self.add_main_option(
            "version",
            ord("v"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Print the version of Lutris and exit"),
            None,
        )
        self.add_main_option(
            "debug",
            ord("d"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Show debug messages"),
            None,
        )
        self.add_main_option(
            "install",
            ord("i"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Install a game from a yml file"),
            None,
        )
        self.add_main_option(
            "force",
            ord("f"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Force updates"),
            None,
        )
        self.add_main_option(
            "output-script",
            ord("b"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Generate a bash script to run a game without the client"),
            None,
        )
        self.add_main_option(
            "exec",
            ord("e"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Execute a program with the Lutris Runtime"),
            None,
        )
        self.add_main_option(
            "list-games",
            ord("l"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("List all games in database"),
            None,
        )
        self.add_main_option(
            "installed",
            ord("o"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Only list installed games"),
            None,
        )
        self.add_main_option(
            "list-steam-games",
            ord("s"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("List available Steam games"),
            None,
        )
        self.add_main_option(
            "list-steam-folders",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("List all known Steam library folders"),
            None,
        )
        self.add_main_option(
            "list-runners",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("List all known runners"),
            None,
        )
        self.add_main_option(
            "list-wine-versions",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("List all known Wine versions"),
            None,
        )
        self.add_main_option(
            "list-all-service-games",
            ord('a'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("List all games for all services in database"),
            None,
        )
        self.add_main_option(
            "list-service-games",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("List all games for provided service in database"),
            None,
        )
        self.add_main_option(
            "install-runner",
            ord("r"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Install a Runner"),
            None,
        )
        self.add_main_option(
            "uninstall-runner",
            ord("u"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Uninstall a Runner"),
            None,
        )
        self.add_main_option(
            "export",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Export a game"),
            None,
        )
        self.add_main_option(
            "import",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Import a game"),
            None,
        )
        self.add_main_option(
            "dest",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Destination path for export"),
            None,
        )
        self.add_main_option(
            "json",
            ord("j"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Display the list of games in JSON format"),
            None,
        )
        self.add_main_option(
            "reinstall",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Reinstall game"),
            None,
        )
        self.add_main_option("submit-issue", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Submit an issue"), None)
        self.add_main_option(
            GLib.OPTION_REMAINING,
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING_ARRAY,
            _("URI to open"),
            "URI",
        )

    def do_startup(self):  # pylint: disable=arguments-differ
        """Sets up the application on first start."""
        Gtk.Application.do_startup(self)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        action = Gio.SimpleAction.new("quit")
        action.connect("activate", lambda *x: self.quit())
        self.add_action(action)
        self.add_accelerator("<Primary>q", "app.quit")

        self.style_manager = StyleManager()

    def do_activate(self):  # pylint: disable=arguments-differ
        if not self.window:
            self.window = LutrisWindow(application=self)
            screen = self.window.props.screen  # pylint: disable=no-member
            Gtk.StyleContext.add_provider_for_screen(screen, self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def show_update_runtime_dialog(self, gpu_info):
        if os.environ.get("LUTRIS_SKIP_INIT"):
            logger.debug("Skipping initialization")
        else:
            pci_ids = [" ".join([gpu["PCI_ID"], gpu["PCI_SUBSYS_ID"]]) for gpu in gpu_info["gpus"].values()]
            runtime_updater = RuntimeUpdater(pci_ids=pci_ids, force=self.force_updates)
            if runtime_updater.has_updates:
                init_dialog = LutrisInitDialog(runtime_updater)
                init_dialog.run()

    def get_window_key(self, **kwargs):
        if kwargs.get("appid"):
            return kwargs["appid"]
        if kwargs.get("runner"):
            return kwargs["runner"].name
        if kwargs.get("installers"):
            return kwargs["installers"][0]["game_slug"]
        if kwargs.get("game"):
            return str(kwargs["game"].get_safe_id())
        return str(kwargs)

    def show_window(self, window_class, **kwargs):
        """Instantiate a window keeping 1 instance max

        Params:
            window_class (Gtk.Window): class to create the instance from
            kwargs (dict): Additional arguments to pass to the instanciated window

        Returns:
            Gtk.Window: the existing window instance or a newly created one
        """
        window_key = str(window_class.__name__) + self.get_window_key(**kwargs)
        if self.app_windows.get(window_key):
            self.app_windows[window_key].present()
            return self.app_windows[window_key]
        if issubclass(window_class, Gtk.Dialog):
            if "parent" in kwargs:
                window_inst = window_class(**kwargs)
            else:
                window_inst = window_class(parent=self.window, **kwargs)
            window_inst.set_application(self)
        else:
            window_inst = window_class(application=self, **kwargs)
        window_inst.connect("destroy", self.on_app_window_destroyed, self.get_window_key(**kwargs))
        self.app_windows[window_key] = window_inst
        logger.debug("Showing window %s", window_key)
        window_inst.show()
        return window_inst

    def show_installer_window(self, installers, service=None, appid=None, installation_kind=InstallationKind.INSTALL):
        self.show_window(
            InstallerWindow,
            installers=installers,
            service=service,
            appid=appid,
            installation_kind=installation_kind
        )

    def on_app_window_destroyed(self, app_window, window_key):
        """Remove the reference to the window when it has been destroyed"""
        window_key = str(app_window.__class__.__name__) + window_key
        try:
            del self.app_windows[window_key]
            logger.debug("Removed window %s", window_key)
        except KeyError:
            logger.warning("Failed to remove window %s", window_key)
            logger.info("Available windows: %s", ", ".join(self.app_windows.keys()))
        return True

    @staticmethod
    def _print(command_line, string):
        # Workaround broken pygobject bindings
        command_line.do_print_literal(command_line, string + "\n")

    def generate_script(self, db_game, script_path):
        """Output a script to a file.
        The script is capable of launching a game without the client
        """
        def on_error(game, error):
            logger.exception("Unable to generate script: %s", error)
            return True

        game = Game(db_game["id"])
        game.connect("game-error", on_error)
        game.reload_config()
        game.write_script(script_path, self.launch_ui_delegate)

    def do_handle_local_options(self, options):
        # Text only commands

        # Print Lutris version and exit
        if options.contains("version"):
            executable_name = os.path.basename(sys.argv[0])
            print(executable_name + "-" + settings.VERSION)
            logger.setLevel(logging.NOTSET)
            return 0
        return -1  # continue command line processes

    def do_command_line(self, command_line):  # noqa: C901  # pylint: disable=arguments-differ
        # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches
        # pylint: disable=too-many-statements
        # TODO: split into multiple methods to reduce complexity (35)
        options = command_line.get_options_dict()

        # Use stdout to output logs, only if no command line argument is
        # provided.
        argc = len(sys.argv) - 1
        if "-d" in sys.argv or "--debug" in sys.argv:
            argc -= 1
        if not argc:
            # Switch back the log output to stderr (the default in Python)
            # to avoid messing with any output from command line options.

            # Use when targeting Python 3.7 minimum
            # console_handler.setStream(sys.stderr)

            # Until then...
            logger.removeHandler(log.console_handler)
            log.console_handler = logging.StreamHandler(stream=sys.stdout)
            log.console_handler.setFormatter(log.SIMPLE_FORMATTER)
            logger.addHandler(log.console_handler)

        # Set up logger
        if options.contains("debug"):
            log.console_handler.setFormatter(log.DEBUG_FORMATTER)
            logger.setLevel(logging.DEBUG)

        if options.contains("force"):
            self.force_updates = True

        init_lutris()

        # Perform migrations early if any command line options
        # might require it to be done, just in case. We migrate
        # also during the init dialog, but it should be harmless
        # to do it twice.
        #
        # This way, in typical lutris usage, you get to see the
        # init dialog when migration is happening.
        if argc:
            migrate()

        gpu_info = run_all_checks()
        if options.contains("dest"):
            dest_dir = options.lookup_value("dest").get_string()
        else:
            dest_dir = None

        # List game
        if options.contains("list-games"):
            game_list = games_db.get_games(filters=(
                {"installed": 1} if options.contains("installed") else None)
            )
            if options.contains("json"):
                self.print_game_json(command_line, game_list)
            else:
                self.print_game_list(command_line, game_list)
            return 0

        # List specified service games
        if options.contains("list-service-games"):
            service = options.lookup_value("list-service-games").get_string()
            game_list = games_db.get_games(filters={"installed": 1, "service": service})
            service_game_list = ServiceGameCollection.get_for_service(service)
            for game in service_game_list:
                game['installed'] = any(('service_id', game['appid']) in item.items() for item in game_list)
            if options.contains("installed"):
                service_game_list = [d for d in service_game_list if d['installed']]
            if options.contains("json"):
                self.print_service_game_json(command_line, service_game_list)
            else:
                self.print_service_game_list(command_line, service_game_list)
            return 0

        # List all service games
        if options.contains("list-all-service-games"):
            game_list = games_db.get_games(filters={"installed": 1})
            service_game_list = ServiceGameCollection.get_service_games()
            for game in service_game_list:
                game['installed'] = any(('service_id', game['appid']) in item.items() for item in game_list if
                                        item['service'] == game['service'])
            if options.contains("installed"):
                service_game_list = [d for d in service_game_list if d['installed']]
            if options.contains("json"):
                self.print_service_game_json(command_line, service_game_list)
            else:
                self.print_service_game_list(command_line, service_game_list)
            return 0

        # List Steam games
        if options.contains("list-steam-games"):
            self.print_steam_list(command_line)
            return 0

        # List Steam folders
        if options.contains("list-steam-folders"):
            self.print_steam_folders(command_line)
            return 0

        # List Runners
        if options.contains("list-runners"):
            self.print_runners()
            return 0

        # List Wine Runners
        if options.contains("list-wine-versions"):
            self.print_wine_runners()
            return 0

        # install Runner
        if options.contains("install-runner"):
            runner = options.lookup_value("install-runner").get_string()
            self.install_runner(runner)
            return 0

        # Uninstall Runner
        if options.contains("uninstall-runner"):
            runner = options.lookup_value("uninstall-runner").get_string()
            self.uninstall_runner(runner)
            return 0

        if options.contains("export"):
            slug = options.lookup_value("export").get_string()
            if not dest_dir:
                print("No destination dir given")
            else:
                export_game(slug, dest_dir)
            return 0

        if options.contains("import"):
            filepath = options.lookup_value("import").get_string()
            if not dest_dir:
                print("No destination dir given")
            else:
                import_game(filepath, dest_dir)
            return 0

        # Execute command in Lutris context
        if options.contains("exec"):
            command = options.lookup_value("exec").get_string()
            self.execute_command(command)
            return 0

        if options.contains("submit-issue"):
            IssueReportWindow(application=self)
            return 0

        url = options.lookup_value(GLib.OPTION_REMAINING)
        try:
            installer_info = self.get_lutris_action(url)
        except ValueError:
            self._print(command_line, _("%s is not a valid URI") % url.get_strv())
            return 1

        game_slug = installer_info["game_slug"]
        action = installer_info["action"]
        service = installer_info["service"]
        appid = installer_info["appid"]
        launch_config_name = installer_info["launch_config_name"]

        self.launch_ui_delegate = CommandLineUIDelegate(launch_config_name)

        if options.contains("output-script"):
            action = "write-script"

        revision = installer_info["revision"]

        installer_file = None
        if options.contains("install"):
            installer_file = options.lookup_value("install").get_string()
            if installer_file.startswith(("http:", "https:")):
                try:
                    request = Request(installer_file).get()
                except HTTPError:
                    self._print(command_line, _("Failed to download %s") % installer_file)
                    return 1
                try:
                    headers = dict(request.response_headers)
                    file_name = headers["Content-Disposition"].split("=", 1)[-1]
                except (KeyError, IndexError):
                    file_name = os.path.basename(installer_file)
                file_path = os.path.join(tempfile.gettempdir(), file_name)
                self._print(command_line, _("download {url} to {file} started").format(
                    url=installer_file, file=file_path))
                with open(file_path, 'wb') as dest_file:
                    dest_file.write(request.content)
                installer_file = file_path
                action = "install"
            else:
                installer_file = os.path.abspath(installer_file)
                action = "install"

            if not os.path.isfile(installer_file):
                self._print(command_line, _("No such file: %s") % installer_file)
                return 1

        db_game = None
        if game_slug and not service:
            if action == "rungameid":
                # Force db_game to use game id
                self.quit_on_game_exit = True
                db_game = games_db.get_game_by_field(game_slug, "id")
            elif action == "rungame":
                # Force db_game to use game slug
                self.quit_on_game_exit = True
                db_game = games_db.get_game_by_field(game_slug, "slug")
            elif action == "install":
                # Installers can use game or installer slugs
                self.quit_on_game_exit = True
                db_game = games_db.get_game_by_field(game_slug, "slug") \
                    or games_db.get_game_by_field(game_slug, "installer_slug")
            else:
                # Dazed and confused, try anything that might works
                db_game = (
                    games_db.get_game_by_field(game_slug, "id")
                    or games_db.get_game_by_field(game_slug, "slug")
                    or games_db.get_game_by_field(game_slug, "installer_slug")
                )

        # If reinstall flag is passed, force the action to install
        if options.contains("reinstall"):
            action = "install"

        if action == "write-script":
            if not db_game or not db_game["id"]:
                logger.warning("No game provided to generate the script")
                return 1
            self.generate_script(db_game, options.lookup_value("output-script").get_string())
            return 0

        # Graphical commands
        self.set_tray_icon()
        self.activate()

        if not action:
            if db_game and db_game["installed"]:
                # Game found but no action provided, ask what to do
                dlg = InstallOrPlayDialog(db_game["name"])
                if not dlg.action:
                    action = "cancel"
                elif dlg.action == "play":
                    action = "rungame"
                elif dlg.action == "install":
                    action = "install"
            elif game_slug or installer_file or service:
                # No game found, default to install if a game_slug or
                # installer_file is provided
                action = "install"

        if service:
            service_game = ServiceGameCollection.get_game(service, appid)
            if service_game:
                service = get_service(service)
                service.install(service_game)
                return 0

        if action == "cancel":
            if not self.window.is_visible():
                self.quit()
            return 0

        if action == "install":
            installers = get_installers(
                game_slug=game_slug,
                installer_file=installer_file,
                revision=revision,
            )
            if installers:
                self.show_installer_window(installers)
        elif action in ("rungame", "rungameid"):
            if not db_game or not db_game["id"]:
                logger.warning("No game found in library")
                if not self.window.is_visible():
                    self.quit()
                return 0

            def on_error(game, error):
                logger.exception("Unable to launch game: %s", error)
                return True

            game = Game(db_game["id"])
            game.connect("game-error", on_error)
            game.launch(self.launch_ui_delegate)

            if game.state == game.STATE_STOPPED and not self.window.is_visible():
                self.quit()
        else:
            self.show_update_runtime_dialog(gpu_info)
            # If we're showing the window, it will handle the delegated UI
            # from here on out, no matter what command line we got.
            self.launch_ui_delegate = self.window
            self.install_ui_delegate = self.window
            self.window.present()
            # If the Lutris GUI is started by itself, don't quit it when a game stops
            self.quit_on_game_exit = False
        return 0

    @watch_errors(error_result=True)
    def on_game_launch(self, game):
        game.launch(self.launch_ui_delegate)
        return True  # Return True to continue handling the emission hook

    @watch_errors(error_result=True)
    def on_game_start(self, game):
        self.running_games.append(game)
        if settings.read_setting("hide_client_on_game_start") == "True":
            self.window.hide()  # Hide launcher window
        return True

    @watch_errors()
    def on_game_stop(self, game):
        """Callback to remove the game from the running games"""
        ids = self.get_running_game_ids()
        if str(game.id) in ids:
            logger.debug("Removing %s from running IDs", game.id)
            try:
                self.running_games.remove(ids.index(str(game.id)))
            except ValueError:
                pass
        elif ids:
            logger.warning("%s not in %s", game.id, ids)
        else:
            logger.debug("Game has already been removed from running IDs?")

        game.emit("game-stopped")
        if settings.read_setting("hide_client_on_game_start") == "True" and not self.quit_on_game_exit:
            self.window.show()  # Show launcher window
        elif not self.window.is_visible():
            if self.running_games.get_n_items() == 0:
                if self.quit_on_game_exit or not self.has_tray_icon():
                    self.quit()
        return True

    @watch_errors(error_result=True)
    def on_game_install(self, game):
        """Request installation of a game"""
        service = get_service(game.service) if game.service else None
        if service and service.type != "lutris":
            db_game = ServiceGameCollection.get_game(service.id, game.appid)
            if not db_game:
                logger.error("Can't find %s for %s", game.name, service.name)
                return True
            try:
                game_id = service.install(db_game)
            except ValueError as e:
                logger.debug(e)
                game_id = None

            if game_id:
                def on_error(game, error):
                    logger.exception("Unable to install game: %s", error)
                    return True

                game = Game(game_id)
                game.connect("game-error", on_error)
                game.launch(self.launch_ui_delegate)
            return True
        if not game.slug:
            raise ValueError("Invalid game passed: %s" % game)
            # return True
        installers = get_installers(game_slug=game.slug)
        if installers:
            self.show_installer_window(installers)
        else:
            ErrorDialog(_("There is no installer available for %s.") % game.name, parent=self.window)
        return True

    @watch_errors(error_result=True)
    def on_game_install_update(self, game):
        service = get_service(game.service)
        db_game = games_db.get_game_by_field(game.id, "id")
        installers = service.get_update_installers(db_game)
        if installers:
            self.show_installer_window(installers, service, game.appid, installation_kind=InstallationKind.UPDATE)
        else:
            ErrorDialog(_("No updates found"), parent=self.window)
        return True

    @watch_errors(error_result=True)
    def on_game_install_dlc(self, game):
        service = get_service(game.service)
        db_game = games_db.get_game_by_field(game.id, "id")
        installers = service.get_dlc_installers_runner(db_game, db_game["runner"])
        if installers:
            self.show_installer_window(installers, service, game.appid, installation_kind=InstallationKind.DLC)
        else:
            ErrorDialog(_("No DLC found"), parent=self.window)
        return True

    def get_running_game_ids(self):
        ids = []
        for i in range(self.running_games.get_n_items()):
            game = self.running_games.get_item(i)
            ids.append(str(game.id))
        return ids

    def get_running_game_by_id(self, game_id):
        for i in range(self.running_games.get_n_items()):
            game = self.running_games.get_item(i)
            if str(game.id) == str(game_id):
                return game
        return None

    def on_watched_error(self, error):
        if self.window:
            ErrorDialog(error, parent=self.window)

    @staticmethod
    def get_lutris_action(url):
        installer_info = {
            "game_slug": None,
            "revision": None,
            "action": None,
            "service": None,
            "appid": None,
            "launch_config_name": None
        }

        if url:
            url = url.get_strv()

        if url:
            url = url[0]
            installer_info = parse_installer_url(url)
            if installer_info is False:
                raise ValueError
        return installer_info

    def print_game_list(self, command_line, game_list):
        for game in game_list:
            self._print(
                command_line,
                "{:4} | {:<40} | {:<40} | {:<15} | {:<64}".format(
                    game["id"],
                    game["name"][:40],
                    game["slug"][:40],
                    game["runner"] or "-",
                    game["directory"] or "-",
                ),
            )

    def print_game_json(self, command_line, game_list):
        games = [
            {
                "id": game["id"],
                "slug": game["slug"],
                "name": game["name"],
                "runner": game["runner"],
                "platform": game["platform"] or None,
                "year": game["year"] or None,
                "directory": game["directory"] or None,
                "hidden": bool(game["hidden"]),
                "playtime": (
                    str(timedelta(hours=game["playtime"]))
                    if game["playtime"] else None
                ),
                "lastplayed": (
                    str(datetime.fromtimestamp(game["lastplayed"]))
                    if game["lastplayed"] else None
                )
            } for game in game_list
        ]
        self._print(command_line, json.dumps(games, indent=2))

    def print_service_game_list(self, command_line, game_list):
        for game in game_list:
            self._print(
                command_line,
                "{:4} | {:<40} | {:<40} | {:<15} | {:<15}".format(
                    game["id"],
                    game["name"][:40],
                    game["slug"][:40],
                    game["service"][:15],
                    "true" if game["installed"] else "false"[:15],
                ),
            )

    def print_service_game_json(self, command_line, game_list):
        games = [
            {
                "id": game["id"],
                "slug": game["slug"],
                "name": game["name"],
                "service": game["service"],
                "installed": game["installed"],
                "details": game["details"]
            } for game in game_list
        ]
        self._print(command_line, json.dumps(games, indent=2))

    def print_steam_list(self, command_line):
        steamapps_paths = get_steamapps_dirs()
        for path in steamapps_paths if steamapps_paths else []:
            appmanifest_files = get_appmanifests(path)
            for appmanifest_file in appmanifest_files:
                appmanifest = AppManifest(os.path.join(path, appmanifest_file))
                self._print(
                    command_line,
                    " {:8} | {:<60} | {}".format(
                        appmanifest.steamid,
                        appmanifest.name or "-",
                        ", ".join(appmanifest.states),
                    ),
                )

    @staticmethod
    def execute_command(command):
        """Execute an arbitrary command in a Lutris context
        with the runtime enabled and monitored by a MonitoredCommand
        """
        logger.info("Running command '%s'", command)
        monitored_command = exec_command(command)
        try:
            GLib.MainLoop().run()
        except KeyboardInterrupt:
            monitored_command.stop()

    def print_steam_folders(self, command_line):
        steamapps_paths = get_steamapps_dirs()
        if steamapps_paths:
            for path in steamapps_paths:
                self._print(command_line, path)

    def print_runners(self):
        runner_names = get_runner_names()
        sorted_names = sorted(runner_names, key=lambda x: x.lower())
        for name in sorted_names:
            print(name)

    def print_wine_runners(self):
        runnersName = get_runners("wine")
        for i in runnersName["versions"]:
            if i["version"]:
                print(i)

    def install_runner(self, runner):
        if runner.startswith("lutris"):
            self.install_wine_cli(runner)
        else:
            self.install_cli(runner)

    def uninstall_runner(self, runner):
        if "wine" in runner:
            print("Are sure you want to delete Wine and all of the installed runners?[Y/N]")
            ans = input()
            if ans.lower() in ("y", "yes"):
                self.uninstall_runner_cli(runner)
            else:
                print("Not Removing Wine")
        elif runner.startswith("lutris"):
            self.wine_runner_uninstall(runner)
        else:
            self.uninstall_runner_cli(runner)

    def install_wine_cli(self, version):
        """
        Downloads wine runner using lutris -r <runner>
        """

        WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
        runner_path = os.path.join(WINE_DIR, f"{version}{'' if '-x86_64' in version else '-x86_64'}")
        if os.path.isdir(runner_path):
            print(f"Wine version '{version}' is already installed.")
        else:
            try:
                runner = import_runner("wine")
                runner().install(self.install_ui_delegate, version=version)
                print(f"Wine version '{version}' has been installed.")
            except (InvalidRunner, RunnerInstallationError) as ex:
                print(ex.message)

    def wine_runner_uninstall(self, version):
        version = f"{version}{'' if '-x86_64' in version else '-x86_64'}"
        WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
        runner_path = os.path.join(WINE_DIR, version)
        if os.path.isdir(runner_path):
            system.remove_folder(runner_path)
            print(f"Wine version '{version}' has been removed.")
        else:
            print(f"""
Specified version of Wine is not installed: {version}.
Please check if the Wine Runner and specified version are installed (for that use --list-wine-versions).
Also, check that the version specified is in the correct format.
                """)

    def install_cli(self, runner_name):
        """
        install the runner provided in prepare_runner_cli()
        """

        try:
            runner = import_runner(runner_name)()
            if runner.is_installed():
                print(f"'{runner_name}' is already installed.")
            else:
                runner.install(self.install_ui_delegate, version=None, callback=None)
                print(f"'{runner_name}' has been installed")
        except (InvalidRunner, RunnerInstallationError) as ex:
            print(ex.message)

    def uninstall_runner_cli(self, runner_name):
        """
        uninstall the runner given in application file located in lutris/gui/application.py
        provided using lutris -u <runner>
        """
        try:
            runner_class = import_runner(runner_name)
            runner = runner_class()
        except InvalidRunner:
            logger.error("Failed to import Runner: %s", runner_name)
            return
        if not runner.is_installed():
            print(f"Runner '{runner_name}' is not installed.")
            return
        if runner.can_uninstall():
            runner.uninstall()
            print(f"'{runner_name}' has been uninstalled.")
        else:
            print(f"Runner '{runner_name}' cannot be uninstalled.")

    def do_shutdown(self):  # pylint: disable=arguments-differ
        logger.info("Shutting down Lutris")
        if self.window:
            selected_category = "%s:%s" % self.window.selected_category
            settings.write_setting("selected_category", selected_category)
            self.window.destroy()
        Gtk.Application.do_shutdown(self)

    def set_tray_icon(self):
        """Creates or destroys a tray icon for the application"""
        active = settings.read_setting("show_tray_icon", default="false").lower() == "true"
        if active and not self.tray:
            self.tray = LutrisStatusIcon(application=self)
        if self.tray:
            self.tray.set_visible(active)

    def has_tray_icon(self):
        return self.tray and self.tray.is_visible()
