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

from gi.repository import Gtk, Gio, GLib

from lutris import pga
from lutris.util import extract
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util.files import calculate_md5

from lutris.runners.steam import steam
from lutris.game import Game
from lutris.config import LutrisConfig
from lutris.gui.dialogs import FileDialog, ErrorDialog, NoticeDialog
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


def background_job(job, cancellable, data):
    task = data['task']
    args = data['args']
    callback = data.get('callback')
    task(args)
    if callback:
        callback()


class ScriptInterpreter(object):
    """ Class that converts raw script data to actions """

    def __init__(self, game_ref, parent):
        self.errors = []
        self.target_path = None
        self.parent = parent
        self.game_name = None
        self.game_slug = None
        self.game_files = {}
        self.steam_data = {}
        self.script = self._fetch_script(game_ref)
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
                raise ScriptingError("Server unreachable", full_url)
        return yaml.safe_load(script_contents)

    def is_valid(self):
        """ Return True if script is usable """
        required_fields = ('runner', 'name')
        for field in required_fields:
            if not self.script.get(field):
                self.errors.append("Missing field '%s'" % field)
        return not bool(self.errors)

    def iter_game_files(self):
        files = self.script.get('files', [])
        if not os.path.exists(self.download_cache_path) and files:
            os.mkdir(self.download_cache_path)

        if not os.path.exists(self.target_path) and files:
            os.makedirs(self.target_path)

        if len(self.game_files) < len(files):
            logger.info(
                "Downloading file %d of %d",
                len(self.game_files) + 1, len(self.script["files"])
            )
            self._download_file(self.script["files"][len(self.game_files)])
        else:
            self.current_command = 0
            self._iter_commands()

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
        elif file_uri.startswith("$WINESTEAM"):
            parts = file_uri.split(":", 2)
            steam_rel_path = parts[2].strip()
            if steam_rel_path == "/":
                steam_rel_path = "."
            self.steam_data = {
                'appid': parts[1],
                'steam_rel_path': steam_rel_path,
                'file_id': file_id
            }
            steam_runner = steam()
            if not steam_runner.is_installed():
                steam_installer_path = os.path.join(
                    settings.TMP_PATH, "SteamInstall.msi"
                )
                self.parent.start_download(
                    steam.installer_url,
                    steam_installer_path,
                    self.parent.on_steam_downloaded,
                    self.steam_data['appid']
                )
                return
            self.install_steam_game()
            return
        logger.debug("Fetching [%s]: %s" % (file_id, file_uri))

        # Check for file availability in PGA
        pga_uri = pga.check_for_file(self.game_slug, file_id)
        if pga_uri:
            file_uri = pga_uri

        # Setup destination path
        dest_file = os.path.join(self.download_cache_path, filename)

        if file_uri == "N/A":
            #Ask the user where is located the file
            file_uri = self.parent.ask_user_for_file()
            if not file_uri:
                raise ScriptingError(
                    "Can't continue installation without file", file_id
                )
            if file_uri.startswith("file://"):
                print file_uri
                self.game_files[file_id] = file_uri[7:]
                self.iter_game_files()
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

    def _iter_commands(self):
        if os.path.exists(self.target_path):
            os.chdir(self.target_path)
        self.parent.set_status("Installing game data")
        self.parent.add_spinner()

        commands = self.script.get('installer', [])
        if self.current_command < len(commands):
            command = commands[self.current_command]
            self.current_command += 1
            method, params = self._map_command(command)
            Gio.io_scheduler_push_job(background_job,
                                      {'task': method, 'args': params,
                                       'callback': self._iter_commands},
                                      GLib.PRIORITY_DEFAULT_IDLE, None)
        else:
            self._finish_install()

    def _finish_install(self):
        self.parent.set_status("Writing configuration")
        self._write_config()
        self._cleanup()
        self.parent.set_status("Installation finished !")
        self.parent.on_install_finished()

    def _cleanup(self):
        if os.path.exists(self.download_cache_path):
            shutil.rmtree(self.download_cache_path)

    def _write_config(self):
        """Write the game configuration as a Lutris launcher."""
        config_filename = os.path.join(settings.CONFIG_DIR,
                                       "games/%s.yml" % self.game_slug)
        runner_name = self.script['runner']
        config_data = {
            'game': {},
            'realname': self.script['name'],
            'runner': runner_name
        }
        pga.add_or_update(self.script['name'], runner_name,
                          slug=self.game_slug,
                          directory=self.target_path)
        if 'system' in self.script:
            config_data['system'] = self.script['system']
        if runner_name in self.script:
            config_data[runner_name] = self.script[runner_name]
        if 'game' in self.script:
            for key in self.script['game']:
                value = self._substitute(self.script['game'][key])
                config_data['game'][key] = value

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
                    config_data['game'][key] = resource_paths
                else:
                    if game_resource in self.game_files:
                        game_resource = self.game_files[game_resource]
                    elif os.path.exists(os.path.join(self.target_path,
                                                     game_resource)):
                        game_resource = os.path.join(self.target_path,
                                                     game_resource)
                    else:
                        game_resource = game_resource
                    config_data['game'][key] = game_resource

        yaml_config = yaml.safe_dump(config_data, default_flow_style=False)
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
            command_params = ""
        command_name = command_name.replace("-", "_")
        command_name = command_name.strip("_")
        if not hasattr(self, command_name):
            raise ScriptingError("The command %s does not exists"
                                 % command_name)
        return getattr(self, command_name), command_params

    def _substitute(self, path_ref):
        """ Replace path aliases with real paths """
        if path_ref.startswith("$GAMEDIR"):
            path_ref = path_ref.replace("$GAMEDIR", self.target_path)
        elif path_ref.startswith("$CACHE"):
            path_ref = path_ref.replace("$CACHE", settings.CACHE_DIR)
        elif path_ref.startswith("$HOME"):
            path_ref = path_ref.replace("$HOME", os.path.expanduser("~"))
        return path_ref

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

    def insert_disc(self, data):
        NoticeDialog("Insert game disc to continue")

    def chmodx(self, filename):
        filename = self._substitute(filename)
        os.popen('chmod +x %s' % filename)

    def execute(self, data):
        """Run an executable script"""
        if isinstance(data, dict):
            exec_id = data['file']
            args = [self._substitute(arg)
                    for arg in data.get('args', '').split()]
        else:
            exec_id = data
            args = []
        exec_path = self.game_files[exec_id]
        if not os.path.exists(exec_path):
            raise ScriptingError("Unable to find required executable",
                                 exec_path)
        else:
            self.chmodx(exec_path)
            logger.debug("Executing %s %s" % (exec_path, args))
            subprocess.call([exec_path] + args)

    def check_md5(self, data):
        filename = self.game_files.get(data['file'])
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
        if not os.path.exists(dst):
            os.makedirs(dst)
        for (dirpath, dirnames, filenames) in os.walk(src):
            src_relpath = dirpath[len(src) + 1:]
            dst_abspath = os.path.join(dst, src_relpath)
            for dirname in dirnames:
                new_dir = os.path.join(dst_abspath, dirname)
                logger.debug("creating dir: %s" % new_dir)
                try:
                    os.mkdir(new_dir)
                except OSError:
                    pass
            for filename in filenames:
                logger.debug("Copying %s" % filename)
                shutil.copy(os.path.join(dirpath, filename),
                            os.path.join(dst_abspath, filename))

    def move(self, params):
        """ Move a file or directory """
        src, dst = self._get_move_paths(params)
        if not os.path.exists(src):
            self.errors.append("I can't move %s, it does not exist" % src)
            return False
        if not os.path.exists(dst):
            os.makedirs(dst)
        target = os.path.join(dst, os.path.basename(src))
        if os.path.exists(target):
            self.errors.append("Destination %s already exists" % target)
        try:
            shutil.move(src, target)
        except shutil.Error:
            self.errors.append("Can't move %s to destination %s" % (src, dst))
            return False
        return True

    def extract(self, data):
        """ Extracts a file, guessing the compression method """
        logger.debug("extracting file %s" % str(data))
        filename = self.game_files.get(data['file'])
        if not filename:
            raise ScriptingError("No file for '%s' in game files %s "
                                 % (data, self.game_files))
            return False
        if not os.path.exists(filename):
            logger.error("%s does not exists" % filename)
            return False
        if 'dst' in data:
            dest_path = self._substitute(data['dst'])
        else:
            dest_path = self.target_path
        msg = "Extracting %s" % filename
        logger.debug(msg)
        self.parent.set_status(msg)
        try:
            extract.extract_archive(filename, dest_path)
        except RuntimeError as ex:
            raise ScriptingError("Failed to extract %s" % filename, ex.message)
        time.sleep(1)

    def _get_steam_game_path(self):
        logger.debug("get steam path")
        steam_runner = steam()
        data_path = steam_runner.get_game_data_path(self.steam_data['appid'])
        if not data_path:
            logger.debug("Game not installed")
            return
        logger.debug("got data path: %s" % data_path)
        self.game_files[self.steam_data['file_id']] = os.path.join(
            data_path,
            self.steam_data['steam_rel_path']
        )
        self.iter_game_files()

    def runner_task(self, data):
        """ This action triggers a task within a runner.
            Mandatory parameters in data are 'task' and 'args'
        """
        logger.info("Called runner task")
        logger.debug(data)
        logger.debug("runner is %s", self.script['runner'])
        runner_name = self.script["runner"]
        task = import_task(runner_name, data['task'])
        args = data['args']
        for key in args:
            if args[key] == "$GAMEDIR":
                args[key] = self.game_dir
            if key == 'filename':
                if args[key] in self.game_files.keys():
                    args[key] = self.game_files[args[key]]
        logger.debug("args are %s", repr(args))
        # FIXME pass args as kwargs and not args
        task(**args)

    def install_steam_game(self):
        steam_runner = steam()
        if not steam_runner.get_game_data_path(self.steam_data['appid']):
            self.steam_install_game(self.steam_data['appid'])
        else:
            self._get_steam_game_path()

    def complete_steam_install(self, dest, appid):
        self.parent.wait_for_user_action(
            "Steam will now install, press Ok when install is finished",
            self.on_steam_installed,
            appid
        )
        steam_runner = steam()
        Gio.io_scheduler_push_job(background_job,
                                  {'task': steam_runner.install, 'args': dest},
                                  GLib.PRIORITY_DEFAULT_IDLE, None)

    def on_steam_installed(self, *args):
        self.install_steam_game()

    def steam_install_game(self, appid):
        logger.debug("Installing steam game %s" % self.steam_data['appid'])
        self.parent.wait_for_user_action(
            "Steam will now install game %s, "
            "press Ok when install is finished" % self.steam_data['appid'],
            self.on_steam_game_installed,
            appid
        )
        steam_runner = steam()
        steam_runner.appid = appid

        Gio.io_scheduler_push_job(
            background_job,
            {'task': steam_runner.install_game, 'args': appid},
            GLib.PRIORITY_DEFAULT_IDLE, None
        )

    def on_steam_game_installed(self, *args):
        logger.debug("Steam game installed")
        self._get_steam_game_path()


# pylint: disable=R0904
class InstallerDialog(Gtk.Dialog):
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

    def __init__(self, game_ref):
        Gtk.Dialog.__init__(self)

        # Dialog properties
        self.set_size_request(600, 480)
        self.set_default_size(600, 480)
        self.set_resizable(False)

        # Default signals
        self.connect('destroy', lambda q: Gtk.main_quit())

        # Interpreter
        self.interpreter = ScriptInterpreter(game_ref, self)

        ## GUI Setup

        # Title label
        title_label = Gtk.Label()
        game_name = self.interpreter.game_name
        title_label.set_markup("<b>Installing {}</b>".format(game_name))
        self.vbox.pack_start(title_label, False, False, 20)

        self.status_label = Gtk.Label()
        self.vbox.pack_start(self.status_label, False, False, 15)

        # Main widget box
        self.widget_box = Gtk.VBox()
        self.widget_box.set_margin_right(25)
        self.widget_box.set_margin_left(25)
        self.vbox.pack_start(self.widget_box, True, True, 15)

        # Separator
        self.vbox.pack_start(Gtk.HSeparator(), False, False, 0)

        # Install button
        self.install_button = Gtk.Button('Install')
        self.install_button.connect('clicked', self.on_install_clicked)

        self.action_buttons = Gtk.Alignment.new(0.95, 0, 0.15, 0)
        self.action_buttons.add(self.install_button)

        self.vbox.pack_start(self.action_buttons, False, False, 25)

        # Target chooser
        if not self.interpreter.requires:
            # Top label
            label = Gtk.Label()
            label.set_markup('<b>Select installation directory:</b>')
            label.set_alignment(0, 0)
            self.widget_box.pack_start(label, False, False, 10)
            default_path = self.interpreter.default_target
            location_entry = FileChooserEntry(default=default_path)
            location_entry.entry.connect('changed', self.on_target_changed)
            self.widget_box.pack_start(location_entry, False, False, 0)
        else:
            label = Gtk.Label("Click install to continue")
        self.show_all()

    def on_target_changed(self, text_entry):
        """ Sets the installation target for the game """
        self.interpreter.target_path = text_entry.get_text()

    def on_install_clicked(self, button):
        button.set_sensitive(False)
        self.interpreter.iter_game_files()

    def ask_user_for_file(self):
        dlg = FileDialog()
        return dlg.filename

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

    def wait_for_user_action(self, message, callback, data):
        self.clean_widgets()
        label = Gtk.Label(message)
        self.widget_box.add(label)
        label.show()
        button = Gtk.Button('Ok')
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

        self.install_button.destroy()
        play_button = Gtk.Button("Launch game")
        play_button.show()
        play_button.connect('clicked', self.launch_game)
        self.action_buttons.add(play_button)

    def launch_game(self, _widget, _data=None):
        """Launch a game after it's been installed"""
        game = Game(self.interpreter.game_slug)
        game.play()
