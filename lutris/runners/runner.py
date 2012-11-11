# -*- coding:Utf-8 -*-
""" Generic runner """
import subprocess
import platform
import hashlib

from lutris.config import LutrisConfig
from lutris.gui.common import ErrorDialog
from lutris.util.log import logger


class Runner(object):
    """Generic runner (base class for other runners) """
    def __init__(self):
        """ Initialize runner """
        self.executable = None
        self.is_installable = False
        self.arguments = []
        self.error_messages = []
        self.game = None
        self.depends = None

    @property
    def description(self):
        """Return the class' docstring as the description"""
        return self.__doc__

    @description.setter
    def description(self, value):
        """Leave the ability to override the docstring"""
        self.__doc__ = value

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

        classname = "lutris.runners." + self.depends
        parts = classname.split('.')
        module = ".".join(parts[:-1])
        module = __import__(module)
        for component in parts[1:]:
            module = getattr(module, component)
        runner = getattr(module, self.depends)
        runner_instance = runner()
        return runner_instance.is_installed()

    def is_installed(self):
        """Return  True if runner is installed else False"""
        is_installed = False
        if not self.executable:
            return False
        result = subprocess.Popen(['which', self.executable],
                                  stdout=subprocess.PIPE).communicate()[0]
        if result == '':
            is_installed = False
        else:
            is_installed = True
        return is_installed

    def get_game_path(self):
        """Seems suspicious, but still useful"""
        logger.warning("get_game_path called, I'm 12 and what is this ?")
        if hasattr(self, 'game_path'):
            path = self.game_path
        else:
            path = None
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
        linux_dist = platform.dist()[0]

        #Add the package manager with arguments for your favorite distro :)
        if linux_dist == 'Ubuntu' or linux_dist == 'Debian':
            package_manager = 'software-center'
            install_args = ''
        elif linux_dist == 'Fedora':
            package_manager = 'yum'
            install_args = 'install'
        else:
            logger.error("The distribution you're running is not supported.")
            logger.error("Edit runners/runner.py to add support for it")
            return False
        if self.package is None:
            ErrorDialog('This runner is not yet installable')
            logger.error("The requested runner %s can't be installed",
                         self.__class__.__name__)
            return

        subprocess.Popen("%s %s %s" % (package_manager, install_args,
                                       self.package),
                         shell=True, stderr=subprocess.PIPE)
        return True

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
