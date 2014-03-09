# pylint: disable=E1101, E0611
"""Installer module"""
import os
import sys
import yaml
import time
import shutil
import urllib2
import platform
import subprocess
import webbrowser

from gi.repository import Gtk

from lutris import pga
from lutris.util import extract
from lutris.util.jobs import async_call
from lutris.util.log import logger
from lutris.util.strings import slugify, add_url_tags
from lutris.util.system import calculate_md5, substitute, merge_folders

from lutris.runners import winesteam, steam
from lutris.game import Game
from lutris.config import LutrisConfig
from lutris.gui.config_dialogs import AddGameDialog
from lutris.gui.dialogs import ErrorDialog, NoInstallerDialog
from lutris.gui.widgets import DownloadProgressBox, FileChooserEntry
from lutris import settings
from lutris.runners import import_task


class ScriptingError(Exception):
    """ Custom exception for scripting errors, can be caught by modifying
    excepthook """
    def __init__(self, message, faulty_data=None):
        self.message = message
        self.faulty_data = faulty_data
        logger.error(self.message + repr(self.faulty_data))
        super(ScriptingError, self).__init__()

    def __str__(self):
        return self.message + "\n" + repr(self.faulty_data)

    def __repr__(self):
        return self.message

_excepthook = sys.excepthook


def error_handler(error_type, value, traceback):
    if error_type == ScriptingError:
        message = value.message
        if value.faulty_data:
            message += "\n<b>" + str(value.faulty_data) + "</b>"
        ErrorDialog(message)
    else:
        _excepthook(error_type, value, traceback)
sys.excepthook = error_handler


class ScriptInterpreter(object):
    """ Class that converts raw script data to actions """

    def __init__(self, game_ref, parent):
        self.error = None
        self.errors = []
        self.files = []
        self.target_path = None
        self.parent = parent
        self.game_name = None
        self.game_slug = None
        self.game_files = {}
        self.steam_data = {}
        self.script = self._fetch_script(game_ref)
        if not self.script:
            return
        if not self.is_valid():
            raise ScriptingError("Invalid script", (self.script, self.errors))
        self.game_name = self.script.get('name')
        self.game_slug = slugify(self.game_name)
        self.requires = self.script.get('requires')
        if self.requires:
            self._check_dependecy()
        else:
            self.target_path = self.default_target

    @property
    def default_target(self):
        lutris_config = LutrisConfig(runner=self.script['runner'])
        games_dir = lutris_config.get_path() or os.path.expanduser('~')
        return os.path.join(games_dir, self.game_slug)

    @property
    def download_cache_path(self):
        return os.path.join(settings.CACHE_DIR,
                            "installer/%s" % self.game_slug)

    @property
    def should_create_target(self):
        return (not os.path.exists(self.target_path)
                and 'nocreatedir' not in self.script)

    def _check_dependecy(self):
        game = pga.get_game_by_slug(self.requires)
        if not game or not game['directory']:
            raise ScriptingError(
                "You need to install {} before".format(self.requires)
            )
        self.target_path = game['directory']

    def _fetch_script(self, game_ref):
        if os.path.exists(game_ref):
            script_contents = open(game_ref, 'r').read()
        else:
            full_url = settings.INSTALLER_URL + game_ref + '.yml'
            request = urllib2.Request(url=full_url)
            try:
                request = urllib2.urlopen(request)
                script_contents = request.read()
            except IOError:
                dlg = NoInstallerDialog(self.parent)
                if dlg.result == 1:
                    game = Game(game_ref)
                    game_dialog = AddGameDialog(self.parent, game)
                    if game_dialog.runner_name:
                        self.parent.notify_install_success()
                elif dlg.result == 2:
                    installer_url = settings.SITE_URL + "games/%s/" % game_ref
                    webbrowser.open(installer_url)
                return
        return yaml.safe_load(script_contents)

    def is_valid(self):
        """ Return True if script is usable """
        required_fields = ('runner', 'name')
        for field in required_fields:
            if not self.script.get(field):
                self.errors.append("Missing field '%s'" % field)

        self.files = self.script.get('files', [])
        return not bool(self.errors)

    def iter_game_files(self):
        if self.files:
            # Create cache dir if needed
            if not os.path.exists(self.download_cache_path):
                os.mkdir(self.download_cache_path)

            if self.should_create_target:
                os.makedirs(self.target_path)

        if len(self.game_files) < len(self.files):
            logger.info(
                "Downloading file %d of %d",
                len(self.game_files) + 1, len(self.script["files"])
            )
            try:
                self._download_file(self.script["files"][len(self.game_files)])
            except KeyError:
                raise ScriptingError("Badly formatted script", self.script)
        else:
            self.current_command = 0
            self._prepare_commands()

    def _download_file(self, game_file):
        """Download a file referenced in the installer script

           Game files can be either a string, containing the location of the
           file to fetch or a dict with the following keys:
           - url : location of file, if not present, filename will be used
                   this should be the case for local files
           - filename : force destination filename when url is present or path
                        of local file
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
            if parts[0] == '$WINESTEAM':
                self.steam_data['platform'] = "windows"
                # Getting data from Wine Steam
                steam_runner = winesteam.winesteam()
                if not steam_runner.is_installed():
                    # Downoad Steam for Windows
                    steam_installer_path = os.path.join(
                        settings.TMP_PATH, "SteamInstall.msi"
                    )
                    self.parent.start_download(
                        winesteam.winesteam.installer_url,
                        steam_installer_path,
                        self.parent.on_steam_downloaded,
                        self.steam_data['appid']
                    )
                else:
                    self.install_steam_game(winesteam.winesteam)
                return
            else:
                # Getting data from Linux Steam
                self.steam_data['platform'] = "linux"
                self.install_steam_game(steam.steam)
                return
        logger.debug("Fetching [%s]: %s" % (file_id, file_uri))

        # Check for file availability in PGA
        pga_uri = pga.check_for_file(self.game_slug, file_id)
        if pga_uri:
            file_uri = pga_uri

        # Setup destination path
        dest_file = os.path.join(self.download_cache_path, filename)

        if file_uri.startswith("N/A"):
            # Ask the user where is located the file
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
        self.parent.set_status('Fetching %s' % file_uri)
        self.game_files[file_id] = dest_file
        self.parent.start_download(file_uri, dest_file)

    def file_selected(self, file_path):
        file_id = self.current_file_id
        if not file_path or not os.path.exists(file_path):
            raise ScriptingError(
                "Can't continue installation without file", file_id
            )
        self.game_files[file_id] = file_path
        self.iter_game_files()

    def _prepare_commands(self):
        if os.path.exists(self.target_path):
            os.chdir(self.target_path)
        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):
        if result == 'STOP':
            return

        self.parent.set_status("Installing game data")
        self.parent.add_spinner()

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
            async_call(method, self._iter_commands, params)
        else:
            self._finish_install()

    def _finish_install(self):
        self.parent.set_status("Writing configuration")
        self._write_config()
        self.parent.set_status("Installation finished !")
        self.parent.on_install_finished()

    def _install_error(self, message):
        self.parent.set_status(message)

    def cleanup(self):
        if os.path.exists(self.download_cache_path):
            shutil.rmtree(self.download_cache_path)

    def _substitute_config(self, script_config):
        """ Substitutes values such as $GAMEDIR in a config dict """
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

    def _write_config(self):
        """Write the game configuration as a Lutris launcher."""
        config_filename = os.path.join(settings.CONFIG_DIR,
                                       "games/%s.yml" % self.game_slug)
        runner_name = self.script['runner']
        config = {
            'game': {},
            'realname': self.script['name'],
            'runner': runner_name
        }
        pga.add_or_update(self.script['name'], runner_name,
                          slug=self.game_slug,
                          directory=self.target_path,
                          installed=1,
                          installer_slug=self.script.get('installer_slug'))
        if 'system' in self.script:
            config['system'] = self._substitute_config(self.script['system'])
        if runner_name in self.script:
            config[runner_name] = self._substitute_config(
                self.script[runner_name]
            )
        if 'game' in self.script:
            config['game'] = self._substitute_config(self.script['game'])
        is_64bit = platform.machine() == "x86_64"
        exe = 'exe64' if 'exe64' in self.script and is_64bit else 'exe'
        for launcher in [exe, 'iso', 'rom', 'disk', 'main_file']:
            if launcher in self.script:
                if launcher == "exe64":
                    key = "exe"
                else:
                    key = launcher
                game_resource = self.script[launcher]
                if type(game_resource) == list:
                    resource_paths = []
                    for res in game_resource:
                        if res in self.game_files:
                            resource_paths.append(self.game_files[res])
                        else:
                            resource_paths.append(res)
                    config['game'][key] = resource_paths
                else:
                    if game_resource in self.game_files:
                        game_resource = self.game_files[game_resource]
                    elif os.path.exists(os.path.join(self.target_path,
                                                     game_resource)):
                        game_resource = os.path.join(self.target_path,
                                                     game_resource)
                    else:
                        game_resource = game_resource
                    config['game'][key] = game_resource

        yaml_config = yaml.safe_dump(config, default_flow_style=False)
        logger.debug(yaml_config)
        with open(config_filename, "w") as config_file:
            config_file.write(yaml_config)

    def _map_command(self, command_data):
        """ Converts a line from the installer directive an internal method """
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

    def _substitute(self, template_string):
        """ Replace path aliases with real paths """
        replacements = {
            "GAMEDIR": self.target_path,
            "CACHE": settings.CACHE_DIR,
            "HOME": os.path.expanduser("~")
        }
        replacements.update(self.game_files)
        return substitute(template_string, replacements)

    def _get_move_paths(self, params):
        """ Validate and converts raw data passed to 'move' """
        for required_param in ('dst', 'src'):
            if required_param not in params:
                raise ScriptingError(
                    "The '%s' parameter is required for 'move'"
                    % required_param, params
                )
        src_ref = params['src']
        src = (self.game_files.get(src_ref) or self._substitute(src_ref))
        if not src:
            raise ScriptingError("Wrong value for 'src' param", src_ref)
        dst_ref = params['dst']
        dst = self._substitute(dst_ref)
        if not dst:
            raise ScriptingError("Wrong value for 'dst' param", dst_ref)
        return (src, dst)

    def _get_file(self, fileid):
        return self.game_files.get(fileid)

    def insert_disc(self, data):
        message = data.get('message', "Insert game disc to continue")
        requires = data.get('requires')
        if not requires:
            raise ScriptingError("The installer's `insert_disc` command is "
                                 "missing the `requires` parameter." * 2)
        self.parent.wait_for_user_action(message, self.on_cd_mounted, requires)
        return 'STOP'

    def on_cd_mounted(self, widget, requires):
        paths = ['/mnt', '/media/cdrom', '/cdrom',
                 '/media/%s/disk' % os.getlogin()]
        for path in paths:
            required_abspath = os.path.join(path, requires)
            if os.path.exists(required_abspath):
                self.game_files['CDROM'] = path
                self._iter_commands()

    def chmodx(self, filename):
        filename = self._substitute(filename)
        os.popen('chmod +x "%s"' % filename)

    def execute(self, data):
        """Run an executable script"""
        if isinstance(data, dict):
            exec_id = data['file']
            args = [self._substitute(arg)
                    for arg in data.get('args', '').split()]
        else:
            exec_id = data
            args = []
        exec_path = self._get_file(exec_id)
        if not exec_path:
            raise ScriptingError("Unable to find file %s" % exec_id, exec_id)
        if not os.path.exists(exec_path):
            raise ScriptingError("Unable to find required executable",
                                 exec_path)
        else:
            self.chmodx(exec_path)
            logger.debug("Executing %s %s" % (exec_path, args))
            subprocess.call([exec_path] + args)

    def check_md5(self, data):
        filename = self._get_file(data['file'])
        _hash = calculate_md5(filename)
        if _hash != data['value']:
            raise ScriptingError("MD5 checksum mismatch", data)

    def mkdir(self, directory):
        directory = self._substitute(directory)
        try:
            os.makedirs(directory)
        except OSError:
            logger.debug("Directory %s already exists" % directory)
        else:
            logger.debug("Created directory %s" % directory)

    def merge(self, params):
        src, dst = self._get_move_paths(params)
        logger.debug("Merging %s into %s" % (src, dst))
        if not os.path.exists(src):
            raise ScriptingError("Source does not exist: %s" % src, params)
        if not os.path.exists(dst):
            os.makedirs(dst)
        if os.path.isfile(src):
            # If single file, copy it and change reference in game file so it
            # can be used as executable. Skip copying if the source is the same
            # as destination.
            if os.path.dirname(src) != dst:
                shutil.copy(src, dst)
            if params['src'] in self.game_files.keys():
                self.game_files[params['src']] = os.path.join(
                    dst, os.path.basename(src)
                )
            return
        merge_folders(src, dst)

    def move(self, params):
        """ Move a file or directory """
        src, dst = self._get_move_paths(params)
        logger.debug("Moving %s to %s" % (src, dst))
        if not os.path.exists(src):
            raise ScriptingError("I can't move %s, it does not exist" % src)
        # TODO: fix behavior of 'move' in existing scripts
        #if not os.path.exists(dst):
        #    os.makedirs(dst)
        #target = os.path.join(dst, os.path.basename(src))
        #if os.path.exists(target):
        #    raise ScriptingError("Destination %s already exists" % target)
        if os.path.isfile(src) and os.path.dirname(src) == dst:
            logger.info("Source file is the same as destination, skipping")
        else:
            try:
                shutil.move(src, dst)
            except shutil.Error:
                raise ScriptingError("Can't move %s to destination %s"
                                    % (src, dst))
        if os.path.isfile(src) and params['src'] in self.game_files.keys():
            # Change game file reference so it can be used as executable
            self.game_files['src'] = src

    def extract(self, data):
        """ Extracts a file, guessing the compression method """
        if not 'file' in data:
            raise ScriptingError('"file" parameter is mandatory for the '
                                 'extract command', data)
        filename = self._get_file(data['file'])
        if not filename:
            filename = self._substitute(data['file'])

        if not os.path.exists(filename):
            raise ScriptingError("%s does not exists" % filename)
        if 'dst' in data:
            dest_path = self._substitute(data['dst'])
        else:
            dest_path = self.target_path
        msg = "Extracting %s" % filename
        logger.debug(msg)
        self.parent.set_status(msg)
        merge_single = not 'nomerge' in data
        extractor = data.get('format')
        logger.debug("extracting file %s to %s", filename, dest_path)
        extract.extract_archive(filename, dest_path, merge_single, extractor)

    def _append_steam_data_to_files(self, runner_class):
        steam_runner = runner_class()
        data_path = steam_runner.get_game_data_path(self.steam_data['appid'])
        if not data_path or not os.path.exists(data_path):
            raise ScriptingError("Unable to get Steam data for game")
        logger.debug("got data path: %s" % data_path)
        self.game_files[self.steam_data['file_id']] = \
            os.path.join(data_path, self.steam_data['steam_rel_path'])
        self.iter_game_files()

    def task(self, data):
        """ This action triggers a task within a runner.
            The 'name' parameter is mandatory. If 'args' is provided it will be
            passed to the runner task.
        """
        task_name = data.pop('name')
        runner_name = self.script["runner"]
        for key in data:
            data[key] = self._substitute(data[key])
        task = import_task(runner_name, task_name)
        task(**data)

    def install_steam_game(self, runner_class):
        steam_runner = runner_class()
        appid = self.steam_data['appid']
        if not steam_runner.get_game_data_path(appid):
            logger.debug("Installing steam game %s" % appid)
            # Here the user must wait for the game to finish installing, a
            # better way to handle this would be to poll StateFlags on the
            # game's config to check if the game has finished installing.
            self.parent.wait_for_user_action(
                "Steam will now install game %s, "
                "press Ok when install is finished" % appid,
                self.on_steam_game_installed,
                appid
            )
            steam_runner.appid = appid
            async_call(steam_runner.install_game, None, appid)
        else:
            self._append_steam_data_to_files(runner_class)

    def complete_steam_install(self, dest, appid):
        self.parent.wait_for_user_action(
            "Steam will now install, press Ok when install is finished",
            self.on_winesteam_installed,
            appid
        )
        steam_runner = winesteam.winesteam()
        async_call(steam_runner.install, None, dest)

    def on_winesteam_installed(self, *args):
        self.install_steam_game(winesteam.winesteam)

    def on_steam_game_installed(self, *args):
        logger.debug("Steam game installed")
        if self.steam_data['platform'] == 'windows':
            runner_class = winesteam.winesteam
        else:
            runner_class = steam.steam
        self._append_steam_data_to_files(runner_class)


# pylint: disable=R0904
class InstallerDialog(Gtk.Window):
    """ Gtk Dialog used during the install process """
    game_dir = None
    download_progress = None

    # # Fetch assets
    # banner_url = settings.INSTALLER_URL + '%s.jpg' % self.game_slug
    # banner_dest = join(settings.DATA_DIR, "banners/%s.jpg" % self.game_slug)
    # http.download_asset(banner_url, banner_dest, True)
    # icon_url = settings.INSTALLER_URL + 'icon/%s.jpg' % self.game_slug
    # icon_dest = join(settings.DATA_DIR, "icons/%s.png" % self.game_slug)
    # http.download_asset(icon_url, icon_dest, True)

    def __init__(self, game_ref, parent=None):
        Gtk.Window.__init__(self)
        self.parent = parent
        self.game_ref = game_ref
        # Dialog properties
        self.set_size_request(600, 480)
        self.set_default_size(600, 480)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        # Default signals
        self.connect('destroy', self.on_destroy)

        # Interpreter
        self.interpreter = ScriptInterpreter(game_ref, self)
        if not self.interpreter.script:
            return

        ## GUI Setup

        # Title label
        title_label = Gtk.Label()
        game_name = self.interpreter.game_name
        title_label.set_markup("<b>Installing {}</b>".format(game_name))
        self.vbox.pack_start(title_label, False, False, 20)

        self.status_label = Gtk.Label()
        self.status_label.set_max_width_chars(80)
        self.status_label.set_property('wrap', True)
        self.status_label.set_selectable(True)
        self.vbox.pack_start(self.status_label, False, False, 15)

        # Main widget box
        self.widget_box = Gtk.VBox()
        self.widget_box.set_margin_right(25)
        self.widget_box.set_margin_left(25)
        self.vbox.pack_start(self.widget_box, True, True, 15)

        self.location_entry = None

        # Separator
        self.vbox.pack_start(Gtk.HSeparator(), False, False, 0)

        # Buttons
        action_buttons_alignment = Gtk.Alignment.new(0.95, 0, 0.15, 0)
        self.action_buttons = Gtk.HBox()
        action_buttons_alignment.add(self.action_buttons)
        self.vbox.pack_start(action_buttons_alignment, False, True, 20)

        self.install_button = Gtk.Button(label='Install')
        self.install_button.connect('clicked', self.on_install_clicked)
        self.action_buttons.add(self.install_button)

        self.continue_button = Gtk.Button(label='Continue')
        self.continue_button.set_margin_left(20)
        self.continue_button.connect('clicked', self.on_file_selected)
        self.action_buttons.add(self.continue_button)

        self.play_button = Gtk.Button(label="Launch game")
        self.play_button.set_margin_left(20)
        self.play_button.connect('clicked', self.launch_game)
        self.action_buttons.add(self.play_button)

        self.close_button = Gtk.Button(label="Close")
        self.close_button.set_margin_left(20)
        self.close_button.connect('clicked', self.close)
        self.action_buttons.add(self.close_button)

        # Target chooser
        if not self.interpreter.requires and self.interpreter.files:
            self.set_message("Select installation directory")
            default_path = self.interpreter.default_target
            self.set_location_entry(self.on_target_changed, default_path)
            self.non_empty_label = Gtk.Label()
            self.non_empty_label.set_markup(
                "<b>Warning!</b> The selected path "
                "contains files, installation might not work property."
            )
            self.widget_box.pack_start(self.non_empty_label, False, False, 10)
        else:
            self.set_message("Click install to continue")
        self.show_all()
        self.continue_button.hide()
        self.close_button.hide()
        self.play_button.hide()
        self.show_non_empty_warning()

    def on_destroy(self, widget):
        self.interpreter.cleanup()
        if self.parent:
            self.destroy()
        else:
            Gtk.main_quit()

    def show_non_empty_warning(self):
        if not self.location_entry:
            return
        path = self.location_entry.get_text()
        if os.path.exists(path) and os.listdir(path):
            self.non_empty_label.show()
        else:
            self.non_empty_label.hide()

    def set_message(self, message):
        label = Gtk.Label()
        label.set_markup('<b>%s</b>' % add_url_tags(message))
        label.set_max_width_chars(80)
        label.set_property('wrap', True)
        label.set_alignment(0, 0)
        label.show()
        self.widget_box.pack_start(label, False, False, 10)

    def set_location_entry(self, callback, default_path=None):
        if self.location_entry:
            self.location_entry.destroy()
        self.location_entry = FileChooserEntry(
            action=Gtk.FileChooserAction.OPEN,  default=default_path
        )
        self.location_entry.show_all()
        if callback:
            self.location_entry.entry.connect('changed', callback)
        else:
            self.install_button.set_visible(False)
            self.continue_button.show()
        self.widget_box.pack_start(self.location_entry, False, False, 0)

    def on_target_changed(self, text_entry):
        """ Sets the installation target for the game """
        path = text_entry.get_text()
        self.interpreter.target_path = path
        self.show_non_empty_warning()

    def on_install_clicked(self, button):
        button.set_sensitive(False)
        self.interpreter.iter_game_files()

    def ask_user_for_file(self, message=None):
        self.clean_widgets()
        self.set_message(message)
        self.set_location_entry(None)

    def on_file_selected(self, widget):
        file_path = self.location_entry.get_text()
        logger.debug("User selected file: %s", file_path)
        self.interpreter.file_selected(file_path)

    def clean_widgets(self):
        for child_widget in self.widget_box.get_children():
            child_widget.destroy()

    def set_status(self, text):
        self.status_label.set_text(text)

    def add_spinner(self):
        self.clean_widgets()
        spinner = Gtk.Spinner()
        self.widget_box.pack_start(spinner, True, False, 10)
        spinner.show()
        spinner.start()

    def start_download(self, file_uri, dest_file, callback=None, data=None):
        self.clean_widgets()
        self.download_progress = DownloadProgressBox(
            {'url': file_uri, 'dest': dest_file}, cancelable=True
        )
        callback_function = callback or self.download_complete
        self.download_progress.connect('complete', callback_function, data)
        self.widget_box.pack_start(self.download_progress, False, False, 10)
        self.download_progress.show()
        self.download_progress.start()

    def wait_for_user_action(self, message, callback, data=None):
        time.sleep(0.3)
        self.clean_widgets()
        label = Gtk.Label(label=message)
        self.widget_box.add(label)
        label.show()
        button = Gtk.Button(label='Ok')
        button.connect('clicked', callback, data)
        self.widget_box.add(button)
        button.show()

    def download_complete(self, widget, data, more_data=None):
        """Action called on a completed download"""
        self.interpreter.iter_game_files()

    def on_steam_downloaded(self, widget, data, appid):
        self.interpreter.complete_steam_install(widget.dest, appid)

    def on_install_finished(self):
        """Actual game installation"""
        self.status_label.set_text("Installation finished !")
        self.clean_widgets()
        self.notify_install_success()
        self.continue_button.hide()
        self.install_button.hide()
        self.play_button.show()
        self.close_button.show()

    def notify_install_success(self):
        if self.parent:
            self.parent.view.emit('game-installed', self.game_ref)

    def on_install_error(self, message):
        self.status_label.set_text(message)
        self.clean_widgets()
        self.close_button.show()

    def launch_game(self, widget, _data=None):
        """Launch a game after it's been installed"""
        widget.set_sensitive(False)
        game = Game(self.interpreter.game_slug)
        game.play()

    def close(self, _widget):
        self.destroy()
