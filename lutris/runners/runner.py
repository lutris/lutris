# -*- coding:Utf-8 -*-
""" Generic runner """
import os
import subprocess
import platform
import hashlib

from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import ErrorDialog, DownloadDialog
from lutris.util.extract import extract_archive
from lutris.util.log import logger
from lutris.util.files import find_executable


def get_arch():
    machine = platform.machine()
    if '64' in machine:
        return 'x64'
    elif '86' in machine:
        return 'i386'


class Runner(object):
    """Generic runner (base class for other runners) """
    def __init__(self, settings=None):
        """ Initialize runner """
        self.is_installable = False
        self.game = None
        self.depends = None
        self.arch = get_arch()
        self.logger = logger
        self.settings = settings

    @property
    def description(self):
        """Return the class' docstring as the description"""
        return self.__doc__

    @description.setter
    def description(self, value):
        """Leave the ability to override the docstring"""
        self.__doc__ = value

    @property
    def machine(self):
        self.logger.error("runner.machine accessed, please use platform")
        return self.platform

    def load(self, game):
        """ Load a game """
        self.game = game

    def play(self):
        """dummy method, must be implemented by derived runnners"""
        raise NotImplementedError("Implement the play method in your runner")

    def check_depends(self):
        """Check if all the dependencies for a runner are installed."""
        if not self.depends:
            return True

        classname = "lutris.runners.%s" % str(self.depends)
        parts = classname.split('.')
        module = ".".join(parts[:-1])
        module = __import__(module)
        for component in parts[1:]:
            module = getattr(module, component)
        runner = getattr(module, str(self.depends))
        runner_instance = runner()
        return runner_instance.is_installed()

    def is_installed(self):
        """Return  True if runner is installed else False"""
        is_installed = False
        if not self.executable:
            return False
        if hasattr(self, 'get_executable'):
            if os.path.exists(self.get_executable()):
                return True
        result = find_executable(self.executable)
        if result == '':
            is_installed = False
        else:
            is_installed = True
        return is_installed

    def get_game_path(self):
        """ Return the directory where the game is installed. """
        if hasattr(self, 'game_path'):
            path = self.game_path
        else:
            path = self.settings['system'].get('game_path')
        return path

    def md5sum(self, filename):
        """checks the md5sum of a file, does not belong here"""
        logger.warning("please remove md5sum from Runner")
        md5check = hashlib.md5()
        file_ = open(filename, "rb")
        content = file_.readlines()
        file_.close()
        for line in content:
            md5check.update(line)
        return md5check.hexdigest()

    def install(self):
        """Install runner using package management systems."""

        # Return false if runner has no package, must be then another method
        # and install method should be overridden by the specific runner
        if not hasattr(self, 'package'):
            return False
        if self.is_installable is False:
            ErrorDialog('This runner is not yet installable')
            return False

        package_installer_candidates = (
            'gpk-install-package-name'
            'software-center',
        )
        package_installer = None
        for candidate in package_installer_candidates:
            if find_executable(candidate):
                package_installer = candidate
                break

        if not package_installer:
            logger.error("The distribution you're running is not supported.")
            logger.error("Edit runners/runner.py to add support for it")
            return False

        if not self.package:
            ErrorDialog('This runner is not yet installable')
            logger.error("The requested runner %s can't be installed",
                         self.__class__.__name__)
            return False

        subprocess.Popen("%s %s" % (package_installer, self.package),
                         shell=True, stderr=subprocess.PIPE)
        return True

    def download_and_extract(self, tarball):
        runner_archive = os.path.join(settings.CACHE_DIR, tarball)

        dialog = DownloadDialog(settings.RUNNERS_URL + tarball, runner_archive)
        dialog.run()

        extract_archive(runner_archive, settings.RUNNER_DIR,
                        merge_single=False)
        os.remove(runner_archive)

    def write_config(self, _id, name, fullpath):
        """Write game configuration to settings directory."""
        system = self.__class__.__name__
        index = fullpath.rindex("/")
        exe = fullpath[index + 1:]
        path = fullpath[:index]
        if path.startswith("file://"):
            path = path[7:]
        config = LutrisConfig()
        config.config = {
            "main": {
                "path": path,
                "exe": exe,
                "realname": name,
                "runner": system
            }
        }
        config.save(config_type="game")
