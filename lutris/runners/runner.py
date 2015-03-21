# -*- coding:Utf-8 -*-
"""Generic runner."""
import os
import platform

from gi.repository import Gtk

from lutris import pga
from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui import dialogs
from lutris.util.extract import extract_archive
from lutris.util.log import logger
from lutris.util import system


def get_arch():
    machine = platform.machine()
    if '64' in machine:
        return 'x64'
    elif '86' in machine:
        return 'i386'


class Runner(object):
    """Generic runner (base class for other runners)."""

    is_watchable = True  # Is the game's pid a parent of Lutris ?
    multiple_versions = False
    tarballs = {
        'i386': None,
        'x64': None
    }
    platform = NotImplemented
    game_options = []
    runner_options = []

    def __init__(self, config=None):
        """Initialize runner."""
        self.depends = None
        self.arch = get_arch()
        self.logger = logger
        self.config = config or {}
        self.game_config = self.config.get('game') or {}
        self.game_data = {}
        if config:
            self.game_data = pga.get_game_by_slug(self.config.game)

    @property
    def description(self):
        """Return the class' docstring as the description."""
        return self.__doc__

    @description.setter
    def description(self, value):
        """Leave the ability to override the docstring."""
        self.__doc__ = value

    def options_as_dict(self, options_type):
        """Convert the option list to a dict with option name as keys"""
        if options_type == 'runner':
            options = self.runner_options
        elif options_type == 'game':
            options = self.game_options
        else:
            raise ValueError("Invalid option type %s" % options_type)
        return dict((opt['option'], opt) for opt in options)

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def default_config(self):
        return LutrisConfig(runner=self.name)

    @property
    def runner_config(self):
        config = self.default_config.runner_config.get(self.name) or {}
        if self.config.get(self.name):
            config.update(self.config[self.name])
        return config

    @property
    def system_config(self):
        """Return system config, cascaded from base, runner and game's system
           config.
        """
        base_system_config = LutrisConfig().system_config.get('system', {})

        # Runner level config, overrides system config
        runner_system_config = self.default_config.config.get('system')
        base_system_config.update(runner_system_config)

        # Game level config, takes precedence over everything
        game_system_config = self.config.get('system') or {}
        base_system_config.update(game_system_config)

        return base_system_config

    @property
    def default_path(self):
        """Return the default path where games are installed."""
        return self.system_config.get('game_path')

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        for key in self.game_config:
            if key in ['exe', 'main_file', 'rom', 'disk', 'iso']:
                path = os.path.dirname(self.game_config.get(key))
                if not os.path.isabs(path):
                    path = os.path.join(self.game_path, path)
                return path

        if self.game_data.get('directory'):
            return self.game_data.get('directory')

    @property
    def game_path(self):
        """Return the directory where the game is installed."""
        if self.game_data.get('directory'):
            return self.game_data.get('directory')
        return self.system_config.get('game_path')

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return os.path.expanduser("~/")

    @property
    def machine(self):
        self.logger.error("runner.machine accessed, please use platform")
        return self.platform

    def play(self):
        """Dummy method, must be implemented by derived runnners."""
        raise NotImplementedError("Implement the play method in your runner")

    def install_dialog(self):
        """Ask the user if she wants to install the runner.

        Return success of runner installation.
        """
        dialog = dialogs.QuestionDialog({
            'question': ("The required runner is not installed.\n"
                         "Do you wish to install it now?"),
            'title': "Required runner unavailable"
        })
        if Gtk.ResponseType.YES == dialog.result:
            return self.install()
        return False

    def is_installed(self):
        """Return  True if runner is installed else False."""
        # Check 'get_executable' first
        if hasattr(self, 'get_executable'):
            executable = self.get_executable()
            if executable and os.path.exists(executable):
                return True

        # Fallback to 'executable' attribute (ssytem-wide install)
        if not getattr(self, 'executable', None):
            return False
        return bool(system.find_executable(self.executable))

    def install(self):
        """Install runner using package management systems."""
        tarball = self.tarballs.get(self.arch)
        if tarball:
            self.download_and_extract(tarball)
            return True
        else:
            dialogs.ErrorDialog(
                'This runner is not available for your platform'
            )
            return False

    def download_and_extract(self, tarball, dest=settings.RUNNER_DIR, **opts):
        runner_archive = os.path.join(settings.CACHE_DIR, tarball)
        merge_single = opts.get('merge_single', False)
        source_url = opts.get('source_url', settings.RUNNERS_URL)
        dialogs.DownloadDialog(source_url + tarball, runner_archive)
        if not os.path.exists(runner_archive):
            logger.error("Can't find %s, aborting install", runner_archive)
            dialogs.ErrorDialog("Installation aborted")
            return
        extract_archive(runner_archive, dest, merge_single=merge_single)
        os.remove(runner_archive)

    def remove_game_data(self, game_path=None):
        system.remove_folder(game_path)
