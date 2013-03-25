#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Installer module"""
import os
import yaml
import shutil
import urllib
import urllib2
import platform
import subprocess

from gi.repository import Gtk

from os.path import join, exists

from lutris.util import log
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util.files import calculate_md5
from lutris.game import LutrisGame
from lutris.config import LutrisConfig
from lutris.gui.common import ErrorDialog, FileDialog
from lutris.gui.widgets import DownloadProgressBox, FileChooserEntry
from lutris.shortcuts import create_launcher
from lutris import settings
from lutris.runners import import_task


def unzip(filename, dest=None):
    """Unzips a file"""
    command = ["unzip", '-o', filename]
    if dest:
        command = command + ['-d', dest]
    subprocess.call(command)


def unrar(filename):
    """Unrar a file"""

    subprocess.call(["unrar", "x", filename])


def untar(filename, dest=None, method='gzip'):
    """Untar a file"""
    cwd = os.getcwd()
    if dest is None or not os.path.exists(dest):
        dest = cwd
    logger.debug("Will extract to %s" % dest)
    os.chdir(dest)
    if method == 'gzip':
        compression_flag = 'z'
    elif method == 'bzip2':
        compression_flag = 'j'
    else:
        compression_flag = ''
    cmd = "tar x%sf %s" % (compression_flag, filename)
    log.logger.debug(cmd)
    subprocess.Popen(cmd, shell=True)
    os.chdir(cwd)


def run_installer(filename):
    """Run an installer of .sh or .run type"""
    subprocess.call(["chmod", "+x", filename])
    subprocess.call([filename])


def reporthook(piece, received_bytes, total_size):
    """Follows the progress of a download"""
    print("%d %%" % ((piece * received_bytes) * 100 / total_size))


# pylint: disable=R0904
class Installer(Gtk.Dialog):
    game_dir = None

    """Installer class"""
    def __init__(self, game, installer=False):
        super(Installer, self).__init__()
        self.set_size_request(500, 400)
        self.lutris_config = None  # Internal game config
        if not game:
            msg = "No game specified in this installer"
            logger.error(msg)
            ErrorDialog(msg)
            return
        self.game_name = game  # Name of the game
        self.game_slug = slugify(self.game_name)
        self.description = False
        self.download_index = 0
        self.rules = {}  # Content of yaml file
        self.actions = []
        self.errors = []
        # Essential game information to create Lutris launcher
        self.game_info = {}
        # Dictionary of the files needed to install the game
        self.gamefiles = {}

        if installer is False:
            self.installer_path = join(settings.CACHE_DIR,
                                       self.game_name + ".yml")
        else:
            self.installer_path = installer

        # Install location
        self.status_label = Gtk.Label()
        self.status_label.set_markup('<b>Select installation directory:</b>')
        self.status_label.set_alignment(0, 0)
        self.status_label.set_padding(20, 0)
        self.vbox.pack_start(self.status_label, True, True, 2)

        success = self.pre_install()
        self.location_entry = FileChooserEntry(default=self.game_dir)
        self.location_entry.entry.connect('changed', self.set_game_dir)
        self.vbox.add(self.location_entry)
        if not success:
            logger.error("Unable to install game")
        else:
            logger.info("Ready! Launching installer.")

        self.download_progress = None
        self.set_default_size(600, 480)
        self.set_resizable(False)
        self.connect('destroy', lambda q: Gtk.main_quit())

        banner_path = join(settings.CACHE_DIR,
                           "banners/%s.jpg" % self.game_slug)
        if os.path.exists(banner_path):
            banner = Gtk.Image()
            banner.set_from_file(banner_path)
            self.vbox.pack_start(banner, False, False)

        if self.description:
            description = Gtk.Label()
            description.set_markup(self.description)
            description.set_padding(20, 20)
            self.vbox.pack_start(description, True, True)

        self.widget_box = Gtk.HBox()
        self.vbox.pack_start(self.widget_box, True, True, 0)

        separator = Gtk.HSeparator()
        self.vbox.pack_start(separator, True, True, 10)

        # Install button
        self.install_button = Gtk.Button('Install')
        self.install_button.connect('clicked', self.download_game_files)
        #self.install_button.set_sensitive(False)

        self.action_buttons = Gtk.Alignment.new(0.95, 0.1, 0.15, 0)
        self.action_buttons.add(self.install_button)

        self.vbox.pack_start(self.action_buttons, False, False, 0)
        self.show_all()

    def display_errors(self):
        full_message = "\n\n".join(self.errors)
        ErrorDialog(full_message)

    def download_installer(self):
        """ Save the downloaded installer to disk. """

        full_url = settings.INSTALLER_URL + self.game_slug + '.yml'
        request = urllib2.Request(url=full_url)
        try:
            urllib2.urlopen(request)
        except urllib2.URLError:
            error_msg = "Server is unreachable at %s", full_url
            logger.error(error_msg)
            self.errors.append(error_msg)
            success = False
        else:
            logger.debug("Downloading installer: %s" % full_url)
            urllib.urlretrieve(full_url, self.installer_path)
            success = True
        return success

    def download_asset(self, url, dest, remove_existing=False):
        asset_opener = urllib.URLopener()
        if os.path.exists(dest):
            if remove_existing:
                os.remove(dest)
            else:
                logger.info("Destination %s exists, not overwritting" % dest)
                return
        try:
            asset_opener.retrieve(url, dest)
        except IOError as ex:
            if ex[1] == 404:
                logger.warning("Asset %s not found" % url)
            else:
                logger.error("Error while fetching %s" % url)

    def pre_install(self):
        """
            Reads the installer and checks everything is OK before beginning
            the install process.
        """
        # Fetch assets
        banner_url = settings.BANNER_URL + '%s.jpg' % self.game_slug
        banner_dest = join(settings.DATA_DIR,
                           "banners/%s.jpg" % self.game_slug)
        self.download_asset(banner_url, banner_dest)
        icon_url = settings.ICONS_URL + '%s.png' % self.game_slug
        icon_dest = join(settings.DATA_DIR, "icons/%s.png" % self.game_slug)
        self.download_asset(icon_url, icon_dest)

        # Download installer if not already there.
        success = self.download_installer()
        if not success:
            self.display_errors()
            return False

        # Parse installer file
        success = self.parse_config()
        games_dir = self.lutris_config.get_path()

        if not games_dir:
            logger.debug("No default path for %s games" % self.rules['runner'])
            default_path = join(os.path.expanduser('~'), self.game_slug)
            logger.debug("default path set to %s " % default_path)
            self.game_dir = default_path
            return True

        self.game_dir = join(games_dir, self.game_slug)
        log.logger.debug("Setting default path to : %s", self.game_dir)
        if not os.path.exists(self.game_dir):
            os.mkdir(self.game_dir)
        return success

    def set_game_dir(self, widget):
        self.game_dir = widget.get_text()

    def download_game_files(self, _widget=None, _data=None):
        """ Runs the actions to complete the install. """

        dest_dir = join(settings.CACHE_DIR, "installer/%s" % self.game_slug)
        if not exists(dest_dir):
            log.logger.debug('Creating destination directory %s' % dest_dir)
            os.mkdir(dest_dir)
        self.location_entry.destroy()
        self.install_button.set_sensitive(False)
        self.process_downloads()

    def process_downloads(self):
        """Download each file needed for the game"""
        files = self.rules.get('files', [])
        if self.download_index < len(files):
            logger.info(
                "Downloading file %d of %d",
                self.download_index + 1, len(self.rules["files"])
            )
            logger.debug(self.rules["files"][self.download_index])
            self.download_game_file(self.rules["files"][self.download_index])
        else:
            logger.debug("All files downloaded")
            self.install()

    def download_complete(self, widget=None, data=None):
        """Action called on a completed download"""
        logger.debug("widget: %s", widget)
        logger.debug("data: %s", data)
        self.download_index += 1
        self.process_downloads()

    def download_game_file(self, game_file):
        """Download a file referenced in the installer script

           Game files can be either a string, containing the location of the
           file to fetch or a dict with the possible options :
           - url : location of file, if not present, filename will be used
                   this should be the case for local files
           - filename : force destination filename when url is present or path
                        of local file

            return the path of local file
        """
        file_id = game_file.keys()[0]
        if isinstance(game_file[file_id], dict):
            if 'filename' in game_file[file_id]:
                filename = game_file[file_id]['filename']
            else:
                filename = None
            if 'url' in game_file[file_id]:
                url = game_file[file_id]['url']
            else:
                url = filename
        else:
            url = game_file[file_id]
            filename = None

        log.logger.debug("Fetching [%s]: %s" % (file_id, url))

        # wat?
        if self.download_progress is not None:
            self.download_progress.destroy()

        self.status_label.set_text('Fetching %s' % url)
        dest_dir = join(settings.CACHE_DIR, "installer/%s" % self.game_slug)
        if not filename:
            filename = os.path.basename(url)
        dest_file = os.path.join(dest_dir, filename)
        if os.path.exists(dest_file):
            log.logger.debug("Destination file exists")
            self.gamefiles[file_id] = dest_file
            self.download_complete(data=dest_file)
        elif url == "N/A":
            #Ask the user where is located the file
            dlg = FileDialog()
            filename = dlg.filename
            logger.debug("[%s]: %s" % (file_id, filename))
            if not filename:
                self.errors.append("Installation cancelled")
                return False
            shutil.copy(filename, dest_dir)
            dest_file = os.path.join(dest_dir, os.path.basename(filename))
            self.gamefiles[file_id] = dest_file

            self.download_complete(data=os.path.join(
                dest_dir, os.path.basename(filename)
            ))
        else:
            self.download_progress = DownloadProgressBox({'url': url,
                                                          'dest': dest_file},
                                                         cancelable=False)
            self.gamefiles[file_id] = dest_file
            self.download_progress.connect('complete', self.download_complete)
            self.widget_box.pack_start(self.download_progress, True, True, 10)
            self.download_progress.show()
            self.download_progress.start()

    def install(self):
        """Actual game installation"""
        logger.debug("Running installation")

        if self.download_progress is not None:
            self.download_progress.destroy()
        if not os.path.exists(self.game_dir):
            os.makedirs(self.game_dir)
        os.chdir(self.game_dir)

        for action in self.actions:
            action_name = action.keys()[0]
            action_data = action[action_name]
            mappings = {
                'extract': self._extract,
                'move': self._move,
                'request_media': self._request_media,
                'run': self._run,
                'runner': self._runner_task,
                'check_md5': self._check_md5,
                'delete': self._delete,
            }
            if action_name not in mappings.keys():
                log.logger.error("Action " + action_name + " not supported !")
                continue
            mappings[action_name](action_data)
        if self.errors:
            self.status_label.set_text("Installation error")
            error_label = Gtk.Label()
            error_label.set_line_wrap(True)
            error_label.set_selectable(True)
            error_label.set_markup("\n".join(self.errors))
            error_label.show()
            self.widget_box.pack_start(error_label, True, True, 20)
            return False
        self.status_label.set_text("Writing configuration")
        self.write_config()

        self.status_label.set_text("Installation finished !")

        desktop_btn = Gtk.Button('Create a desktop shortcut')
        desktop_btn.connect(
            'clicked',
            lambda d: create_launcher(self.game_slug, desktop=True)
        )
        menu_btn = Gtk.Button('Create an icon in the application menu')
        menu_btn.connect(
            'clicked',
            lambda m: create_launcher(self.game_slug, menu=True)
        )
        buttons_box = Gtk.HBox()
        buttons_box.pack_start(desktop_btn, False, False, 10)
        buttons_box.pack_start(menu_btn, False, False, 10)
        buttons_box.show_all()

        self.widget_box.pack_start(buttons_box, True, True, 10)

        self.install_button.destroy()
        play_button = Gtk.Button("Launch game")
        play_button.show()
        play_button.connect('clicked', self.launch_game)
        self.action_buttons.add(play_button)

    def parse_config(self):
        """ Reads the installer file. """
        installer_contents = file(self.installer_path, 'r').read()
        self.rules = yaml.safe_load(installer_contents)
        logger.debug("Installer content:\n %s" % installer_contents)

        mandatory_fields = ['runner', 'name']
        optional_fields = ['exe', 'exe64', 'iso', 'rom', 'disk']
        for field in mandatory_fields:
            self.game_info[field] = self.rules[field]
        for field in optional_fields:
            if field in self.rules:
                self.game_info[field] = self.rules[field]

        self.game_name = self.rules['name']
        self.game_slug = os.path.basename(self.installer_path)[:-4]

        self.actions = self.rules['installer']
        self.lutris_config = LutrisConfig(runner=self.game_info['runner'])
        return True

    def write_config(self):
        """Write the game configuration as a Lutris launcher."""
        config_filename = join(settings.CONFIG_DIR,
                               "games/%s.yml" % self.game_slug)
        config_data = {
            'game': {},
            'realname': self.game_info['name'],
            'runner': self.game_info['runner']
        }
        is_64bit = platform.machine() == "x86_64"
        exe = 'exe64' if 'exe64' in self.game_info and is_64bit else 'exe'
        for launcher in [exe, 'iso', 'rom']:
            if launcher in self.game_info:
                if launcher == "exe64":
                    key = "exe"
                else:
                    key = launcher
                launcher_path = join(self.game_dir,
                                     self.game_info[launcher])
                config_data['game'][key] = launcher_path

        yaml_config = yaml.dump(config_data, default_flow_style=False)
        file(config_filename, "w").write(yaml_config)

    def _get_path(self, data):
        """Return a filesystem path based on data"""
        if data == 'parent':
            path = os.path.dirname(self.game_dir)
        else:
            path = self.game_dir
        return path

    def _check_md5(self, data):
        print "MD5"
        calculate_md5(self.gamefiles.get(data))
        print self.gamefiles
        print data

    def _extract(self, data):
        """ Extracts a file, guessing the compression method """
        filename = self.gamefiles.get(data['file'])
        if not filename:
            log.logger.error("No file for '%s' in game files" % data['file'])
            return False
        if not os.path.exists(filename):
            log.logger.error("%s does not exists" % filename)
            return False
        msg = "Extracting %s" % filename
        log.logger.debug(msg)
        self.status_label.set_text(msg)
        _, extension = os.path.splitext(filename)
        if extension == ".zip":
            unzip(filename, self.game_dir)
        elif filename.endswith('.tgz') or filename.endswith('.tar.gz'):
            untar(filename, None)
        elif filename.endswith('.tar.bz2'):
            untar(filename, None, 'bzip2')
        else:
            log.logger.error("unrecognised file extension %s" % extension)
            return False

    def _move(self, data):
        """ Moves a file. """
        file_id = data['src']
        src = self.gamefiles.get(file_id)
        if not src:
            msg = "Can't find %s in %s" % (file_id, self.gamefiles)
            logger.error(msg)
            self.errors.append(msg)
            return False

        if data['dst'] == 'gamedir':
            dst = self.game_dir
        else:
            dst = data['dst'].replace('homedir', os.path.expanduser('~'))
            if not os.path.exists(dst):
                dst = '/tmp'

        self.status_label.set_text("Moving %s" % src)
        logger.debug("[%s] Moving to %s" % (src, dst))
        if not os.path.exists(src):
            msg = "I can't move %s, it does not exist" % src
            logger.error(msg)
            self.errors.append(msg)
            return False
        dest_filename = os.path.join(dst, os.path.basename(src))
        if os.path.exists(dest_filename):
            os.remove(dest_filename)
        try:
            shutil.move(src, dst)
        except shutil.Error:
            msg = "Couln't move %s to destination %s" % (
                src, dst
            )
            logger.error(msg)
            self.errors.append(msg)
            return False
        return True

    def _delete(self, data):
        print "Script has requested to delete %s" % data

    def _request_media(self, data):
        """Prompt user to insert a removable media"""
        path = data.get('default', '')
        if os.path.exists(os.path.join(path, data['contains'])):
            return True
        else:
            return False

    def _run(self, data):
        """Run an executable script"""
        exec_path = os.path.join(settings.CACHE_DIR, self.game_slug,
                                 self.gamefiles[data['file']])
        if not os.path.exists(exec_path):
            print("unable to find %s" % exec_path)
            exit()
        else:
            os.popen('chmod +x %s' % exec_path)
            subprocess.call([exec_path])

    def _runner_task(self, data):
        """ This action triggers a task within a runner.
            Mandatory parameters in data are 'task' and 'args'
        """

        log.logger.info("Called runner task")
        log.logger.debug(data)
        log.logger.debug("runner is %s", self.rules['runner'])
        runner_name = self.rules["runner"]
        task = import_task(runner_name, data['task'])
        args = data['args']
        for key in args:
            if args[key] in ("$GAME_DIR", "$GAMEDIR"):
                args[key] = self.game_dir
            if key == 'filename':
                if args[key] in self.gamefiles.keys():
                    args[key] = self.gamefiles[args[key]]
        log.logger.debug("args are %s", repr(args))
        # FIXME pass args as kwargs and not args
        task(**args)

    def launch_game(self, _widget, _data=None):
        """Launch a game after it's been installed"""
        lutris_game = LutrisGame(self.game_slug)
        lutris_game.play()
