# pylint: disable=E1101, E0611
"""Install a game by following its install script."""
import os
import yaml
import shutil
import urllib2
import platform
import webbrowser

from gi.repository import GLib

from .errors import ScriptingError
from .commands import Commands

from lutris import pga, settings
from lutris.util import system
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.steam import get_app_states

from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.config_dialogs import AddGameDialog
from lutris.gui.dialogs import NoInstallerDialog
from lutris.runners import wine, winesteam, steam


def fetch_script(window, game_ref):
    """Download install script(s) for matching game_ref."""
    request = urllib2.Request(url=settings.INSTALLER_URL % game_ref)
    try:
        request = urllib2.urlopen(request)
        script_contents = request.read()
    except IOError:
        dlg = NoInstallerDialog(window)
        if dlg.result == dlg.MANUAL_CONF:
            game = Game(game_ref)
            game_dialog = AddGameDialog(window, game)
            game_dialog.run()
            if game_dialog.saved:
                window.notify_install_success()
        elif dlg.result == dlg.NEW_INSTALLER:
            installer_url = settings.SITE_URL + "games/%s/" % game_ref
            webbrowser.open(installer_url)
        return
    # Data should be JSON here, but JSON is also valid YAML.
    # At some point we will be dropping the YAML parser and load installer
    # data with json.loads
    return yaml.safe_load(script_contents)


class ScriptInterpreter(Commands):
    """Convert raw installer script data into actions."""
    def __init__(self, script, parent):
        self.error = None
        self.errors = []
        self.files = []
        self.target_path = None
        self.parent = parent
        self.reversion_data = {}
        self.game_name = None
        self.game_slug = None
        self.game_files = {}
        self.game_disc = None
        self.current_download = None
        self.user_inputs = []
        self.steam_data = {}
        self.script = script
        if not self.script:
            return
        if not self.is_valid():
            raise ScriptingError("Invalid script", (self.script, self.errors))
        self.game_name = self.script['name']
        self.game_slug = self.script['game_slug']
        self.requires = self.script.get('requires')
        if self.requires:
            self._check_dependency()
        else:
            self.target_path = self.default_target

    @property
    def default_target(self):
        """Default install dir."""
        config = LutrisConfig(runner_slug=self.script['runner'])
        games_dir = config.system_config.get('game_path',
                                             os.path.expanduser('~'))
        return os.path.join(games_dir, self.game_slug)

    @property
    def download_cache_path(self):
        return os.path.join(settings.CACHE_DIR,
                            "installer/%s" % self.game_slug)

    @property
    def should_create_target(self):
        return (not os.path.exists(self.target_path)
                and 'nocreatedir' not in self.script)

    # --------------------------
    # "Initial validation" stage
    # --------------------------

    def is_valid(self):
        """Return True if script is usable."""
        required_fields = ('runner', 'name', 'game_slug')
        for field in required_fields:
            if not self.script.get(field):
                self.errors.append("Missing field '%s'" % field)

        self.files = self.script.get('files', [])
        return not bool(self.errors)

    def _check_dependency(self):
        # XXX Maybe handle this with Game instead of hitting directly the PGA?
        game = pga.get_game_by_slug(self.requires, field='installer_slug')
        if not game or not game['directory']:
            raise ScriptingError(
                "You need to install {} before".format(self.requires)
            )
        self.target_path = game['directory']

    # ---------------------
    # "Get the files" stage
    # ---------------------

    def iter_game_files(self):
        if self.files:
            # Create cache dir if needed
            if not os.path.exists(self.download_cache_path):
                os.mkdir(self.download_cache_path)

            if self.should_create_target:
                os.makedirs(self.target_path)
                self.reversion_data['created_main_dir'] = True

        if len(self.game_files) < len(self.files):
            logger.info(
                "Downloading file %d of %d",
                len(self.game_files) + 1, len(self.script["files"])
            )
            file_index = len(self.game_files)
            try:
                current_file = self.script["files"][file_index]
            except KeyError:
                raise ScriptingError("Error getting file %d in %s",
                                     file_index, self.script['files'])
            self._download_file(current_file)
        else:
            self.current_command = 0
            self._prepare_commands()

    def _download_file(self, game_file):
        """Download a file referenced in the installer script.

        Game files can be either a string, containing the location of the
        file to fetch or a dict with the following keys:
        - url : location of file, if not present, filename will be used
                this should be the case for local files.
        - filename : force destination filename when url is present or path
                     of local file.
        """
        # Setup file_id, file_uri and local filename
        file_id = game_file.keys()[0]
        if isinstance(game_file[file_id], dict):
            filename = game_file[file_id]['filename']
            file_uri = game_file[file_id]['url']
        else:
            file_uri = game_file[file_id]
            filename = os.path.basename(file_uri)
        if file_uri.startswith("/"):
            file_uri = "file://" + file_uri
        elif file_uri.startswith(("$WINESTEAM", "$STEAM")):
            # Download Steam data
            self._download_steam_data(file_uri, file_id)
            return
        logger.debug("Fetching [%s]: %s" % (file_id, file_uri))

        # Check for file availability in PGA
        pga_uri = pga.check_for_file(self.game_slug, file_id)
        if pga_uri:
            file_uri = pga_uri

        # Setup destination path
        dest_file = os.path.join(self.download_cache_path, filename)

        if file_uri.startswith("N/A"):
            # Ask the user where the file is located
            parts = file_uri.split(":", 1)
            if len(parts) == 2:
                message = parts[1]
            else:
                message = "Please select file '%s'" % file_id
            self.current_file_id = file_id
            self.parent.ask_user_for_file(message)
            return

        if os.path.exists(dest_file):
            logger.debug("Destination file exists")
            if settings.KEEP_CACHED_ASSETS:
                self.game_files[file_id] = dest_file
                self.iter_game_files()
                return
            else:
                os.remove(dest_file)

        # Change parent's status
        self.parent.set_status('')
        self.game_files[file_id] = dest_file
        self.parent.start_download(file_uri, dest_file)

    def _download_steam_data(self, file_uri, file_id):
        """Download the game files from Steam to use them outside of Steam.

        file_uri: Colon separated game info containing:
                   - $STEAM or $WINESTEAM depending on the version of Steam
                     Since Steam for Linux can download games for any
                     platform, using $WINESTEAM has little value except in
                     some cases where the game needs to be started by Steam
                     in order to get a CD key (ie. Doom 3 or UT2004)
                   - The Steam appid
                   - The relative path of files to retrieve
        file_id: The lutris installer internal id for the game files
        """
        try:
            parts = file_uri.split(":", 2)
            steam_rel_path = parts[2].strip()
        except IndexError:
            raise ScriptingError("Malformed steam path: %s" % file_uri)
        if steam_rel_path == "/":
            steam_rel_path = "."
        self.steam_data = {
            'appid': parts[1],
            'steam_rel_path': steam_rel_path,
            'file_id': file_id
        }

        logger.debug(
            "Getting Steam data for appid %s" % self.steam_data['appid']
        )

        if parts[0] == '$WINESTEAM':
            self.parent.set_status('Getting Wine Steam game data')
            self.steam_data['platform'] = "windows"
            # Check that wine is installed
            wine_runner = wine.wine()
            if not wine_runner.is_installed():
                wine_runner.install()
            # Getting data from Wine Steam
            steam_runner = winesteam.winesteam()
            if not steam_runner.is_installed():
                winesteam.download_steam(
                    downloader=self.parent.start_download,
                    callback=self.parent.on_steam_downloaded
                )
            else:
                self.install_steam_game(winesteam.winesteam,
                                        is_game_files=True)
        else:
            # Getting data from Linux Steam
            self.parent.set_status('Getting Steam game data')
            self.steam_data['platform'] = "linux"
            self.install_steam_game(steam.steam, is_game_files=True)

    def file_selected(self, file_path):
        file_id = self.current_file_id
        if not file_path or not os.path.exists(file_path):
            raise ScriptingError(
                "Can't continue installation without file", file_id
            )
        self.game_files[file_id] = file_path
        self.iter_game_files()

    # ---------------
    # "Commands" stage
    # ---------------

    def _prepare_commands(self):
        """Run the pre-installation steps and launch install."""
        if os.path.exists(self.target_path):
            os.chdir(self.target_path)
        runner_name = self.script['runner']

        # Add steam installation to commands if it's a Steam game
        if runner_name in ('steam', 'winesteam'):
            try:
                self.steam_data['appid'] = self.script['game']['appid']
            except KeyError:
                raise ScriptingError("Missing appid for steam game")

            commands = self.script.get('installer', [])
            commands.insert(0, 'install_steam_game')
            self.script['installer'] = commands
        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):
        if result == 'STOP':
            return

        self.parent.set_status("Installing game data")
        self.parent.add_spinner()
        self.parent.continue_button.hide()

        commands = self.script.get('installer', [])
        if exception:
            self.parent.on_install_error(repr(exception))
        elif self.current_command < len(commands):
            command = commands[self.current_command]
            self.current_command += 1
            method, params = self._map_command(command)
            if isinstance(params, dict):
                status_text = params.pop("description", None)
            else:
                status_text = None
            if status_text:
                self.parent.set_status(status_text)
            AsyncCall(method, self._iter_commands, params)
        else:
            self._finish_install()

    def _map_command(self, command_data):
        """Map a directive from the `installer` section to an internal
        method."""
        if isinstance(command_data, dict):
            command_name = command_data.keys()[0]
            command_params = command_data[command_name]
        else:
            command_name = command_data
            command_params = {}
        command_name = command_name.replace("-", "_")
        command_name = command_name.strip("_")
        if not hasattr(self, command_name):
            raise ScriptingError("The command %s does not exists"
                                 % command_name)
        return getattr(self, command_name), command_params

    # ----------------
    # "Finalize" stage
    # ----------------

    def _finish_install(self):
        self.parent.set_status("Writing configuration")
        self._write_config()
        self.parent.set_status("Installation finished !")
        self.parent.on_install_finished()

    def _write_config(self):
        """Write the game configuration in the DB and config file."""
        runner_name = self.script['runner']

        # Get existing config
        config_filename = os.path.join(settings.CONFIG_DIR,
                                       "games/%s.yml" % self.game_slug)
        if self.requires and os.path.exists(config_filename):
            # The installer is patching an existing game, update its config
            # XXX Maybe drop the self.requires condition and always update
            #     the existing config?
            lutris_config = LutrisConfig(runner_slug=runner_name,
                                         game_slug=self.game_slug)
            config = lutris_config.game_level
        else:
            config = {
                'game': {},
            }

        # DB update
        pga.add_or_update(self.script['name'], runner_name,
                          slug=self.game_slug,
                          directory=self.target_path,
                          installed=1,
                          installer_slug=self.script.get('slug'),
                          year=self.script.get('year'),
                          steamid=self.script.get('steamid'))

        # Config update
        if 'system' in self.script:
            config['system'] = self._substitute_config(self.script['system'])
        if runner_name in self.script:
            config[runner_name] = self._substitute_config(
                self.script[runner_name]
            )
        if 'game' in self.script:
            config['game'].update(self._substitute_config(self.script['game']))

        is_64bit = platform.machine() == "x86_64"
        exe = 'exe64' if 'exe64' in self.script and is_64bit else 'exe'

        for launcher in [exe, 'iso', 'rom', 'disk', 'main_file']:
            if launcher not in self.script:
                continue
            launcher_description = self.script[launcher]
            if launcher == "exe64":
                launcher = "exe"
            if type(launcher_description) == list:
                game_files = []
                for game_file in launcher_description:
                    if game_file in self.game_files:
                        game_files.append(self.game_files[game_file])
                    else:
                        game_files.append(game_file)
                config['game'][launcher] = game_files
            else:
                if launcher_description in self.game_files:
                    launcher_description = (
                        self.game_files[launcher_description]
                    )
                elif os.path.exists(os.path.join(self.target_path,
                                                 launcher_description)):
                    launcher_description = os.path.join(self.target_path,
                                                        launcher_description)
                else:
                    launcher_description = launcher_description
                config['game'][launcher] = launcher_description

        yaml_config = yaml.safe_dump(config, default_flow_style=False)
        logger.debug(yaml_config)
        with open(config_filename, "w") as config_file:
            config_file.write(yaml_config)

    def _substitute_config(self, script_config):
        """Substitute values such as $GAMEDIR in a config dict."""
        config = {}
        for key in script_config:
            if not isinstance(key, basestring):
                raise ScriptingError("Game config key must be a string", key)
            value = script_config[key]
            if isinstance(value, list):
                config[key] = [self._substitute(i) for i in value]
            else:
                config[key] = self._substitute(value)
        return config

    # --------------------
    # "Afer the end" stage
    # --------------------

    def cleanup(self):
        if os.path.exists(self.download_cache_path):
            shutil.rmtree(self.download_cache_path)

    # --------------
    # Revert install
    # --------------

    def revert(self):
        # Abort current task
        if self.current_download:
            self.current_download.cancel()

        # Cleanup
        if os.path.exists(self.download_cache_path):
            shutil.rmtree(self.download_cache_path)

        if self.reversion_data.get('created_main_dir'):
            if os.path.exists(self.target_path):
                shutil.rmtree(self.target_path)
            return

    # -------------
    # Utility stuff
    # -------------

    def _substitute(self, template_string):
        """Replace path aliases with real paths."""
        replacements = {
            "GAMEDIR": self.target_path,
            "CACHE": settings.CACHE_DIR,
            "HOME": os.path.expanduser("~"),
            "DISC": self.game_disc,
            "USER": os.getenv('USER'),
            "INPUT": self._get_last_user_input(),
        }
        # Add 'INPUT_<id>' replacements for user inputs with an id
        for input_data in self.user_inputs:
            alias = input_data['alias']
            if alias:
                replacements[alias] = input_data['value']

        replacements.update(self.game_files)
        return system.substitute(template_string, replacements)

    def _get_last_user_input(self):
        return self.user_inputs[-1]['value'] if self.user_inputs else ''

    # -----------
    # Steam stuff
    # -----------

    def install_steam_game(self, runner_class=None, is_game_files=False):
        """Launch installation of a steam game.

        runner_class: class of the steam runner to use
        is_game_files: whether the game is used for the installer game files
        """
        if not runner_class:
            if self.script['runner'] == 'steam':
                runner_class = steam.steam
            elif self.script['runner'] == 'winesteam':
                runner_class = winesteam.winesteam
            else:
                raise ScriptingError('Missing Steam platform')

        steam_runner = runner_class()
        self.steam_data['is_game_files'] = is_game_files
        self.steam_data['steamapps_path'] = (
            steam_runner.get_default_steamapps_path()
        )
        appid = self.steam_data['appid']
        if not steam_runner.get_game_path_from_appid(appid):
            logger.debug("Installing steam game %s" % appid)
            # Here the user must wait for the game to finish installing, a
            # better way to handle this would be to poll StateFlags on the
            # game's config to check if the game has finished installing.
            # self.parent.wait_for_user_action(
            #    "Steam will now download and install game %s, "
            #    "press Ok when it's finished" % appid,
            #    self.on_steam_game_installed,
            #    appid
            # )
            steam_runner.appid = appid
            AsyncCall(steam_runner.install_game, None, appid)
            self.steam_poll = GLib.timeout_add(2000,
                                               self.monitor_steam_install)
            return 'STOP'
        elif is_game_files:
            self._append_steam_data_to_files(runner_class)

    def monitor_steam_install(self):
        steamapps_path = self.steam_data['steamapps_path']
        appid = self.steam_data['appid']
        states = get_app_states(steamapps_path, appid)
        logger.debug(states)
        if 'Fully Installed' in states:
            self.on_steam_game_installed()
            logger.debug('Steam game has finished installing')
            return False
        else:
            logger.debug('Steam game still installing')
            return True

    def on_steam_game_installed(self, *args):
        """Fired whenever a Steam game has finished installing."""
        if self.steam_data['is_game_files']:
            if self.steam_data['platform'] == 'windows':
                runner_class = winesteam.winesteam
            else:
                runner_class = steam.steam
            self._append_steam_data_to_files(runner_class)
        else:
            self._iter_commands()

    def _append_steam_data_to_files(self, runner_class):
        steam_runner = runner_class()
        data_path = steam_runner.get_game_path_from_appid(
            self.steam_data['appid'])
        if not data_path or not os.path.exists(data_path):
            raise ScriptingError("Unable to get Steam data for game")
        logger.debug("got data path: %s" % data_path)
        self.game_files[self.steam_data['file_id']] = \
            os.path.join(data_path, self.steam_data['steam_rel_path'])
        self.iter_game_files()

    def complete_steam_install(self, dest):
        winesteam_runner = winesteam.winesteam()
        AsyncCall(winesteam_runner.install, self.on_winesteam_installed, dest)

    def on_winesteam_installed(self, *args):
        self.install_steam_game(winesteam.winesteam)
