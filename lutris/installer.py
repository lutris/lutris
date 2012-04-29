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
import gtk
import yaml
import shutil
import urllib
import urllib2
import platform
import subprocess
import lutris.constants

from os.path import join, exists

from lutris.util import log
from lutris.util.strings import slugify
from lutris.game import LutrisGame
from lutris.config import LutrisConfig
from lutris.gui.common import ErrorDialog, DirectoryDialog
from lutris.gui.widgets import DownloadProgressBox
from lutris.shortcuts import create_launcher
from lutris.constants import LUTRIS_CACHE_PATH, INSTALLER_URL, TMP_PATH, \
                             ICON_PATH, BANNER_PATH, GAME_CONFIG_PATH


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
    log.logger.debug("Will extract to %s" % dest)
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
    print "%d %%" % ((piece * received_bytes) * 100 / total_size)


class Installer(gtk.Dialog):
    """ Installer class """
    def __init__(self, game, installer=False):
        self.lutris_config = None  # Internal game config
        if not game:
            msg = "No game specified in this installer"
            log.logger.error(msg)
            ErrorDialog(msg)
            return False
        self.game_name = game  # Name of the game
        self.game_slug = slugify(self.game_name)
        self.description = False
        default_path = join(os.path.expanduser('~'), self.game_slug)
        self.game_dir = default_path
        self.rules = {}  # Content of yaml file
        self.actions = []
        self.errors = []
        # Essential game information to create Lutris launcher
        self.game_info = {}
        # Dictionary of the files needed to install the game
        self.gamefiles = {}
        if installer is False:
            self.installer_path = join(LUTRIS_CACHE_PATH,
                                               self.game_name + ".yml")
        else:
            self.installer_path = installer

        self.location_button = gtk.FileChooserButton("Select folder")

        # FIXME: Wrong ! The runner should be loaded first in order to
        # determine its default location
        default_path = os.path.expanduser('~') + self.game_slug

        self.location_button.set_current_folder(default_path)
        self.location_button.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        self.location_button.connect("file-set", self.game_dir_set)

        success = self.pre_install()
        if not success:
            log.logger.error("Unable to install game")
        else:
            log.logger.info("Ready! Launching installer.")

        self.download_progress = None
        gtk.Dialog.__init__(self)
        self.set_default_size(600, 480)
        self.set_resizable(False)
        self.connect('destroy', lambda q: gtk.main_quit())

        banner_path = join(BANNER_PATH, "%s.jpg" % self.game_slug)
        if os.path.exists(banner_path):
            banner = gtk.Image()
            banner.set_from_file(banner_path)
            self.vbox.pack_start(banner, False, False)

        if self.description:
            description = gtk.Label()
            description.set_markup(self.description)
            description.set_padding(20, 20)
            self.vbox.pack_start(description, True, True)

        # Install location
        self.status_label = gtk.Label()
        self.status_label.set_markup('<b>Select installation directory:</b>')
        self.status_label.set_alignment(0, 0)
        self.status_label.set_padding(20, 0)
        self.vbox.pack_start(self.status_label, True, True, 2)

        self.widget_box = gtk.HBox()
        self.vbox.pack_start(self.widget_box)

        self.widget_box.pack_start(self.location_button)

        separator = gtk.HSeparator()
        self.vbox.pack_start(separator, True, True, 10)

        # Install button
        self.install_button = gtk.Button('Install')
        self.install_button.connect('clicked', self.download_game_files)
        #self.install_button.set_sensitive(False)

        self.action_buttons = gtk.Alignment()
        self.action_buttons.set(0.95, 0.1, 0.15, 0)
        self.action_buttons.add(self.install_button)

        self.vbox.pack_start(self.action_buttons, False, False)
        self.show_all()

    def download_installer(self):
        """ Save the downloaded installer to disk. """

        full_url = INSTALLER_URL + self.game_slug + '.yml'
        request = urllib2.Request(url=full_url)
        try:
            urllib2.urlopen(request)
        except urllib2.URLError:
            log.logger.debug("Server is unreachable")
            self.errors.append("INSTALLER_UNREACHABLE")
            success = False
        else:
            urllib.urlretrieve(full_url, self.installer_path)
            success = True
        return success

    def pre_install(self):
        """Reads the installer and checks everything is OK
        before beginning the install process
        """

        # Fetch assets
        banner_url = 'http://lutris.net/media/banners/%s.jpg' % self.game_slug
        banner_dest = join(BANNER_PATH, "%s.jpg" % self.game_slug)
        try:
            urllib.urlretrieve(banner_url, banner_dest)
        except IOError:
            print "cant get banner to %s" % banner_dest

        icon_url = 'http://lutris.net/media/game_icons/%s.png' % self.game_slug
        icon_path = join(ICON_PATH, "%s.png" % self.game_slug)
        try:
            urllib.urlretrieve(icon_url, icon_path)
        except IOError:
            print "cant get icon"

        # Download installer if not already there.
        if not os.path.exists(self.installer_path):
            success = self.download_installer()
            if not success:
                return False
        else:
            log.logger.debug('Using local copy of the installer')

        if 'INSTALLER_UNREACHABLE' in self.errors:
            ErrorDialog("Can't find an installer for \"%s\""
                            % self.game_slug)
            return False

        # Parse installer file
        success = self.parse_config()
        games_dir = self.lutris_config.get_path()

        if not games_dir:
            log.logger.debug("No default path for %s games"
                             % self.rules['runner'])
            return True

        self.game_dir = join(games_dir, self.game_slug)
        if not os.path.exists(self.game_dir):
            os.mkdir(self.game_dir)

        self.location_button.set_current_folder(self.game_dir)
        return success

    def game_dir_set(self, widget=None):
        """Set the installation directory based on the user's choice"""
        self.game_dir = widget.get_current_folder()
        if os.path.exists(self.game_dir):
            self.install_button.set_sensitive(True)

    def download_game_files(self, widget=None, data=None):
        """ Runs the actions to complete the install. """

        self.location_button.destroy()
        self.install_button.set_sensitive(False)

        for game_file in self.rules['files']:
            self.download_game_file(game_file)
        log.logger.debug("All files downloaded")
        self.install()

    def download_game_file(self, game_file):
        """Download a file referenced in the installer script"""
        file_id = game_file.keys()[0]
        # Game files can be either a string, containing the location of the
        # file to fetch or a dict with the possible options :
        # - url : location of file (mandatory)
        # - filename : force destination filename
        # - nocopy : don't copy the file in the cache (not for internet links)
        copyfile = True
        if isinstance(game_file[file_id], dict):
            url = game_file[file_id]['url']
            if 'filename' in game_file[file_id]:
                filename = game_file[file_id]['filename']
            else:
                filename = None

            if 'nocopy' in game_file[file_id]:
                copyfile = False
        else:
            url = game_file[file_id]
            filename = None
        log.logger.debug("Downloading %s" % url)
        dest_path = self._download(url, filename, copyfile)
        self.gamefiles[file_id] = dest_path
        return True

    def install(self):
        log.logger.debug("Running installation")

        if self.download_progress is not None:
            self.download_progress.destroy()
        if not os.path.exists(self.game_dir):
            os.makedirs(self.game_dir)
        os.chdir(self.game_dir)

        for action in self.actions:
            action_name = action.keys()[0]
            action_data = action[action_name]
            mappings = {'check_md5': self.check_md5,
                        'extract': self._extract,
                        'move': self._move,
                        'delete': self.delete,
                        'request_media': self._request_media,
                        'run': self._run}
            if action_name not in mappings.keys():
                print "Action " + action_name + " not supported !"
                return False
            mappings[action_name](action_data)
        self.status_label.set_text("Writing configuration")
        self.write_config()

        self.status_label.set_text("Installation finished !")

        desktop_btn = gtk.Button('Create a desktop shortcut')
        desktop_btn.connect('clicked',
                                     lambda d: create_launcher(self.game_slug,
                                                               desktop=True))
        menu_btn = gtk.Button('Create an icon in the application menu')
        menu_btn.connect('clicked',
                                  lambda m: create_launcher(self.game_slug,
                                                            menu=True))
        buttons_box = gtk.HBox()
        buttons_box.pack_start(desktop_btn, False, False, 10)
        buttons_box.pack_start(menu_btn, False, False, 10)
        buttons_box.show_all()

        self.widget_box.pack_start(buttons_box, True, True, 10)

        self.install_button.destroy()
        play_button = gtk.Button("Launch game")
        play_button.show()
        play_button.connect('clicked', self.launch_game)
        self.action_buttons.add(play_button)

    def parse_config(self):
        """ Reads the installer file. """
        installer_contents = file(self.installer_path, 'r').read()
        self.rules = yaml.load(installer_contents)

        #Checking protocol
        try:
            protocol_version = self.rules['protocol']
        except KeyError:
            log.logger.error("No protocol version specified in installer")
            log.logger.error("Please fix the installer for %s" % self.game)
            return False
        if protocol_version != lutris.constants.protocol_version:
            print("Wrong protocol version (Expected %d, got %d)" %
                  (lutris.constants.protocol_version, protocol_version))
            return False

        mandatory_fields = ['version', 'runner', 'name']
        optional_fields = ['exe', 'exe64', 'iso', 'rom']
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
        config_filename = join(GAME_CONFIG_PATH,
                               self.game_slug + ".yml")

        config_data = {'game': {},
                       'realname': self.game_info['name'],
                       'runner': self.game_info['runner']}
        if 'exe64' in self.game_info and platform.machine() == "x86_64":
            exe = "exe64"
        else:
            exe = "exe"
        launchers = [exe, 'iso', 'rom']

        for launcher in launchers:
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

    def check_md5(self, data):
        """ Calculates the checksum of a file and validates it. """

        print 'checking md5 for file ' + self.gamefiles[data['file']]
        print 'expecting ' + data['value']
        print "NOT IMPLEMENTED"
        return True

    def _download(self, url, filename=None, copyfile=True):
        """ Downloads a file.
        Not necessarily downloading a file but fetching it from anywhere.
        url: location of the file to fetch
        destfile: force filename of destfile

        return the path of local file
        """
        if self.download_progress is not None:
            self.download_progress.destroy()

        self.status_label.set_text('Fetching %s' % url)
        dest_dir = join(TMP_PATH, self.game_slug)
        if not exists(dest_dir):
            log.logger.debug('Creating destination directory %s' % dest_dir)
            os.mkdir(dest_dir)
        if not filename:
            filename = os.path.basename(url)
        dest_file = os.path.join(dest_dir, filename)
        if os.path.exists(dest_file):
            log.logger.debug("Destination file exists")
            return dest_file
        if url.startswith("file://"):
            location = url[7:]
            if copyfile is True:
                shutil.copy(location, dest_dir)
        elif url.startswith("$ASK_DIR"):
            #Ask the user where is located the file
            basename = url[9:]
            dlg = DirectoryDialog("Select location of file %s " % basename)
            file_path = dlg.folder
            if copyfile is True:
                location = os.path.join(file_path, basename)
                shutil.copy(location, dest_dir)
        else:
            self.download_progress = DownloadProgressBox({'url': url,
                                                          'dest': dest_file},
                                                         cancelable=False)
            self.download_progress.connect('complete', self.download_complete)
            self.widget_box.pack_start(self.download_progress, True, True)
            self.download_progress.show()
            self.download_progress.start()

    def download_complete(self, widget, data):
        log.logger.debug("Download complete")

    def delete(self, data):
        """ Deletes a file """
        print "will delete " + self.gamefiles[data['file']]
        print "let's not delete anything right now, m'kay ?"

    def _get_path(self, data):
        """Return a filesystem path based on data"""

        if data == 'parent':
            path = os.path.dirname(self.game_dir)
        else:
            path = self.game_dir
        return path

    def _extract(self, data):
        """ Extracts a file, guessing the compression method """
        filename = self.gamefiles[data['file']]
        if not os.path.exists(filename):
            log.logger.error("%s does not exists" % filename)
            return False
        msg = "Extracting %s" % filename
        log.logger.debug(msg)
        self.status_label.set_text(msg)
        _, extension = os.path.splitext(filename)

        if extension == "zip":
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
        src = data['src']
        self.status_label.set_text("Moving %s" % src)
        if src in self.gamefiles.keys():
            src = self.gamefiles[src]
        if data['dst'] == 'gamedir':
            dst = self.game_dir
        else:
            dst = data['dst'].replace('homedir', os.path.expanduser('~'))
            if not os.path.exists(dst):
                dst = '/tmp'

        print "Moving %s to %s" % (src, dst)

        if not os.path.exists(src):
            print "I cannot move what does not exist"
            return False
        try:
            shutil.move(src, dst)
        except shutil.Error:
            print "Could not move the file, destination already exists ?"
            return False
        return True

    def _request_media(self, data):
        """Prompt user to insert a removable media"""
        if 'default' in data:
            path = data['default']
        if os.path.exists(os.path.join(path, data['contains'])):
            return True
        else:
            return False

    def _run(self, data):
        """Run an executable script"""
        exec_path = os.path.join(TMP_PATH, self.game_slug,
                                 self.gamefiles[data['file']])
        if not os.path.exists(exec_path):
            print "unable to find %s" % exec_path
            exit()
        else:
            os.popen('chmod +x %s' % exec_path)
            subprocess.call([exec_path])

    def launch_game(self, **kwargs):
        """Launch a game after it's been installed"""
        lutris_game = LutrisGame(self.game_slug)
        lutris_game.play()
