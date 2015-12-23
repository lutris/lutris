# pylint: disable=E1101, E0611
"""Install a game by following its install script."""
import os
import time
import yaml
import shutil
import urllib2
import platform

from gi.repository import GLib

from .errors import ScriptingError
from .commands import Commands

from lutris import pga, settings
from lutris.util import system
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.steam import get_app_state_log

from lutris.config import LutrisConfig, make_game_config_id
from lutris.runners import wine, winesteam, steam


def fetch_script(game_ref):
    """Download install script(s) for matching game_ref."""
    request = urllib2.Request(url=settings.INSTALLER_URL % game_ref)
    try:
        request = urllib2.urlopen(request)
        script_contents = request.read()
    except IOError:
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
        self.target_path = None
        self.parent = parent
        self.reversion_data = {}
        self.game_name = None
        self.game_slug = None
        self.game_files = {}
        self.game_disc = None
        self.cancelled = False
        self.abort_current_task = None
        self.user_inputs = []
        self.steam_data = {}
        self.script = script
        if not self.script:
            return
        if not self.is_valid():
            raise ScriptingError("Invalid script", (self.script, self.errors))

        self.files = self.script.get('files', [])
        self.runner = self.script['runner']
        self.game_name = self.script['name']
        self.game_slug = self.script['game_slug']
        self.requires = self.script.get('requires')
        if self.requires:
            self._check_dependency()
        if self.creates_game_folder:
            self.target_path = self.get_default_target()

        # If the game is in the library and uninstalled, the first installation
        # updates it
        existing_game = pga.get_game_by_field(self.game_slug, 'slug')
        if existing_game and not existing_game['installed']:
            self.game_id = existing_game['id']
        else:
            self.game_id = None

    def get_default_target(self):
        """Return default installation dir"""
        config = LutrisConfig(runner_slug=self.runner)
        games_dir = config.system_config.get('game_path',
                                             os.path.expanduser('~'))
        return os.path.expanduser(os.path.join(games_dir, self.game_slug))

    @property
    def download_cache_path(self):
        return os.path.join(settings.CACHE_DIR,
                            "installer/%s" % self.game_slug)

    @property
    def should_create_target(self):
        return (
            not os.path.exists(self.target_path)
            and 'nocreatedir' not in self.script
            and self.creates_game_folder
        )

    @property
    def creates_game_folder(self):
        if self.requires:
            # Game is an extension of an existing game, folder exists
            return False
        if self.runner in ('steam', 'winesteam'):
            # Steam games installs in their steamapps directory
            return False
        if self.files:
            return True
        if self.runner in ('linux', 'wine', 'dosbox'):
            # Can use 'insert-disc' and have no files
            return True
        return False

    # --------------------------
    # "Initial validation" stage
    # --------------------------

    def is_valid(self):
        """Return True if script is usable."""
        required_fields = ('runner', 'name', 'game_slug')
        for field in required_fields:
            if not self.script.get(field):
                self.errors.append("Missing field '%s'" % field)
        return not bool(self.errors)

    def _check_dependency(self):
        # XXX Maybe handle this with Game instead of hitting directly the PGA?
        game = pga.get_game_by_field(self.requires, field='installer_slug')
        # Legacy support of installers using game slug as requirement
        if not game:
            game = pga.get_game_by_field(self.requires, 'slug')

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

            if self.target_path and self.should_create_target:
                os.makedirs(self.target_path)
                self.reversion_data['created_main_dir'] = True

        if len(self.game_files) < len(self.files):
            logger.info(
                "Downloading file %d of %d",
                len(self.game_files) + 1, len(self.files)
            )
            file_index = len(self.game_files)
            try:
                current_file = self.files[file_index]
            except KeyError:
                raise ScriptingError("Error getting file %d in %s",
                                     file_index, self.files)
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

        self.parent.clean_widgets()
        self.parent.add_spinner()
        if parts[0] == '$WINESTEAM':
            self.parent.set_status('Getting Wine Steam game data')
            self.steam_data['platform'] = "windows"
            self.install_steam_game(winesteam.winesteam,
                                    is_game_files=True)
        else:
            # Getting data from Linux Steam
            self.parent.set_status('Getting Steam game data')
            self.steam_data['platform'] = "linux"
            self.install_steam_game(steam.steam, is_game_files=True)

    def check_steam_install(self):
        """Checks that the required version of Steam is installed.
        Return a boolean indicating whether is it or not.
        """
        if self.steam_data['platform'] == 'windows':
            # Check that wine is installed
            wine_runner = wine.wine()
            if not wine_runner.is_installed():
                logger.debug('Wine is not installed')
                wine_runner.install(
                    downloader=self.parent.start_download,
                    callback=self.check_steam_install
                )
                return False
            # Getting data from Wine Steam
            steam_runner = winesteam.winesteam()
            if not steam_runner.is_installed():
                logger.debug('Winesteam not installed')
                winesteam.download_steam(
                    downloader=self.parent.start_download,
                    callback=self.on_steam_downloaded
                )
                return False
            return True
        else:
            steam_runner = steam.steam()
            if not steam_runner.is_installed():
                raise ScriptingError(
                    "Install Steam for Linux and start installer again"
                )
            return True

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
        if self.target_path and os.path.exists(self.target_path):
            os.chdir(self.target_path)

        # Add steam installation to commands if it's a Steam game
        if self.runner in ('steam', 'winesteam'):
            try:
                self.steam_data['appid'] = self.script['game']['appid']
            except KeyError:
                raise ScriptingError("Missing appid for steam game")

            commands = self.script.get('installer', [])
            self.steam_data['platform'] = 'windows' \
                if self.runner == 'winesteam' else 'linux'
            commands.insert(0, 'install_steam_game')
            self.script['installer'] = commands
        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):
        if result == 'STOP' or self.cancelled:
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

    def _get_game_launcher(self):
        """Return the key and value of the launcher"""
        launcher_value = None
        is_64bit = platform.machine() == "x86_64"
        exe = 'exe64' if 'exe64' in self.script and is_64bit else 'exe'

        for launcher in [exe, 'iso', 'rom', 'disk', 'main_file']:
            if launcher not in self.script:
                continue
            launcher_value = self.script[launcher]
            if launcher == "exe64":
                launcher = "exe"
            break
        if not launcher_value:
            logger.error('No launcher provided in %s', self.script)
        return (launcher, launcher_value)

    def _write_config(self):
        """Write the game configuration in the DB and config file."""

        configpath = make_game_config_id(self.script['slug'])
        config_filename = os.path.join(settings.CONFIG_DIR,
                                       "games/%s.yml" % configpath)
        if self.requires:  # and os.path.exists(config_filename):
            # The installer is patching an existing game, update its config
            # XXX Maybe drop the self.requires condition and always update
            #     the existing config?
            # XXX Now it's not going to update configs ever again since we
            # create a unique config_id so how do we deal with that?

            # is that okay?
            required_game = pga.get_game_by_field(self.requires,
                                                  field='installer_slug')
            lutris_config = LutrisConfig(
                runner_slug=self.runner,
                game_config_id=required_game['configpath']
            )
            config = lutris_config.game_level
        else:
            config = {
                'game': {},
            }

        self.game_id = pga.add_or_update(
            name=self.script['name'],
            runner=self.runner,
            slug=self.game_slug,
            directory=self.target_path,
            installed=1,
            installer_slug=self.script['slug'],
            parent_slug=self.requires,
            year=self.script.get('year'),
            steamid=self.script.get('steamid'),
            configpath=configpath,
            id=self.game_id
        )
        logger.debug("Saved game entry %s (%d)", self.game_slug, self.game_id)

        # Config update
        if 'system' in self.script:
            config['system'] = self._substitute_config(self.script['system'])
        if self.runner in self.script:
            config[self.runner] = self._substitute_config(
                self.script[self.runner]
            )
        if 'game' in self.script:
            config['game'].update(self._substitute_config(self.script['game']))

        launcher, launcher_value = self._get_game_launcher()
        if type(launcher_value) == list:
            game_files = []
            for game_file in launcher_value:
                if game_file in self.game_files:
                    game_files.append(self.game_files[game_file])
                else:
                    game_files.append(game_file)
            config['game'][launcher] = game_files
        elif launcher_value:
            if launcher_value in self.game_files:
                launcher_value = (
                    self.game_files[launcher_value]
                )
            elif self.target_path and os.path.exists(
                os.path.join(self.target_path, launcher_value)
            ):
                launcher_value = os.path.join(self.target_path, launcher_value)
            config['game'][launcher] = launcher_value

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
            elif isinstance(value, dict):
                config[key] = dict(
                    [(k, self._substitute(v)) for (k, v) in value.iteritems()]
                )
            else:
                config[key] = self._substitute(value)
        return config

    # --------------------
    # "Afer the end" stage
    # --------------------

    def cleanup(self):
        os.chdir(os.path.expanduser('~'))
        if os.path.exists(self.download_cache_path):
            shutil.rmtree(self.download_cache_path)

    # --------------
    # Revert install
    # --------------

    def revert(self):
        logger.debug("Install cancelled")
        self.cancelled = True

        if self.abort_current_task:
            self.abort_current_task()

        if self.reversion_data.get('created_main_dir'):
            if os.path.exists(self.target_path):
                shutil.rmtree(self.target_path)

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
        is_game_files: whether game data is added to game_files
        """

        # Check if Steam is installed, save the method's arguments so it can
        # be called again once Steam is installed.
        self.steam_data['callback_args'] = (runner_class, is_game_files)
        is_installed = self.check_steam_install()
        if not is_installed:
            return 'STOP'

        steam_runner = self._get_steam_runner(runner_class)
        self.steam_data['is_game_files'] = is_game_files
        appid = self.steam_data['appid']
        if not steam_runner.get_game_path_from_appid(appid):
            logger.debug("Installing steam game %s", appid)
            AsyncCall(steam_runner.install_game, None, appid, is_game_files)

            self.install_start_time = time.localtime()
            self.steam_poll = GLib.timeout_add(
                2000, self._monitor_steam_game_install
            )
            self.abort_current_task = (
                lambda: steam_runner.remove_game_data(appid=appid)
            )
            return 'STOP'
        elif is_game_files:
            self._append_steam_data_to_files(runner_class)
        else:
            self.target_path = self._get_steam_game_path()

    def _get_steam_runner(self, runner_class=None):
        if not runner_class:
            if self.runner == 'steam':
                runner_class = steam.steam
            elif self.runner == 'winesteam':
                runner_class = winesteam.winesteam
            elif self.steam_data['is_game_files']:
                if self.steam_data['platform'] == 'windows':
                    runner_class = winesteam.winesteam
                else:
                    runner_class = steam.steam
        return runner_class()

    def _monitor_steam_game_install(self):
        if self.cancelled:
            return False
        appid = self.steam_data['appid']
        steam_runner = self._get_steam_runner()
        states = get_app_state_log(steam_runner.steam_data_dir, appid,
                                   self.install_start_time)
        logger.debug(states)
        if states and states.pop().startswith('Fully Installed'):
            self._on_steam_game_installed()
            logger.debug('Steam game has finished installing')
            return False
        else:
            logger.debug('Steam game still installing')
            return True

    def _on_steam_game_installed(self, *args):
        """Fired whenever a Steam game has finished installing."""
        self.abort_current_task = None
        if self.steam_data['is_game_files']:
            if self.steam_data['platform'] == 'windows':
                runner_class = winesteam.winesteam
            else:
                runner_class = steam.steam
            self._append_steam_data_to_files(runner_class)
        else:
            self.target_path = self._get_steam_game_path()
            self._iter_commands()

    def _get_steam_game_path(self, runner_class=None):
        if not runner_class:
            steam_runner = self._get_steam_runner()
        else:
            steam_runner = runner_class()
        return steam_runner.get_game_path_from_appid(
            self.steam_data['appid']
        )

    def _append_steam_data_to_files(self, runner_class):
        data_path = self._get_steam_game_path(runner_class)
        if not data_path or not os.path.exists(data_path):
            raise ScriptingError("Unable to get Steam data for game")
        logger.debug("got data path: %s" % data_path)
        self.game_files[self.steam_data['file_id']] = \
            os.path.join(data_path, self.steam_data['steam_rel_path'])
        self.iter_game_files()

    def on_steam_downloaded(self, *args):
        logger.debug("Steam downloaded")
        dest = winesteam.get_steam_installer_dest()
        winesteam_runner = winesteam.winesteam()
        AsyncCall(winesteam_runner.install, self.on_winesteam_installed, dest)

    def on_winesteam_installed(self, *args):
        logger.debug("Winesteam installed")
        callback_args = self.steam_data['callback_args']
        self.parent.add_spinner()
        self.install_steam_game(*callback_args)
