# -*- coding:Utf-8 -*-
""" Super Nintendo runner """
import os
import urllib
import platform
import subprocess
import xml.etree.ElementTree as etree

from lutris.util.log import logger
from lutris.runners.runner import Runner
from lutris import settings
from lutris.util.extract import extract_archive, decompress_gz

SNES9X_VERSION = "snes9x-1.53"
SNES9X_32 = settings.RUNNERS_URL + "%s-gtk-81-i386.tar.bz2" % SNES9X_VERSION
SNES9X_64 = settings.RUNNERS_URL + "%s-gtk-81-x86_64.tar.bz2" % SNES9X_VERSION
LIBPNG_32 = NotImplemented
LIBPNG_64 = settings.LIB64_URL + "libpng14.so.14.12.0.gz"

RUNNER_DIR = os.path.join(settings.DATA_DIR, "runners")
SNES9X_RUNNER_DIR = os.path.join(RUNNER_DIR, SNES9X_VERSION)


class snes9x(Runner):
    """Runs Super Nintendo games with Snes9x"""
    def __init__(self, settings=None):
        """It seems that the best snes emulator around it snes9x-gtk
        zsnes has no 64bit port
        """
        super(snes9x, self).__init__()
        self.executable = "snes9x-gtk"
        self.package = None
        self.platform = "Super Nintendo"
        self.is_installable = True
        self.game_options = [{"option": "main_file",
                              "type": "file_chooser",
                              "default_path": "game_path",
                              "label": "ROM"}]
        self.runner_options = [
            {
                "option": "fullscreen",
                "type": "bool",
                "label": "Fullscreen",
                "default": "1"
            },
            {
                "option": "maintain_aspect_ratio",
                "type": "bool",
                "label": "Maintain aspect ratio",
                "default": "1"
            },
            {
                "option": "sound_driver",
                "type": "one_choice",
                "label": "Sound driver",
                "choices": (("OSS", "0"), ("SDL", "1"), ("ALSA", "2")),
                "default": "1"
            }
        ]
        if settings:
            self.rom = settings["game"]["main_file"]
            self.settings = settings

    def options_as_dict(self):
        option_dict = {}
        for option in self.runner_options:
            option_dict[option['option']] = option
        return option_dict

    def play(self):
        """Run Super Nintendo game"""
        options = self.options_as_dict()
        runner_options = self.settings.get('snes9x')
        for option_name in options:
            if runner_options:
                self.set_option(
                    option_name,
                    runner_options.get(
                        option_name, options[option_name].get('default')
                    )
                )
        return {'command': self.get_executable() + ["\"%s\"" % self.rom]}

    def get_executable(self):
        local_path = os.path.join(SNES9X_RUNNER_DIR, self.executable)
        lib_path = os.path.join(SNES9X_RUNNER_DIR, "lib")
        if os.path.exists(local_path):
            executable = ["LD_LIBRARY_PATH=\"%s\"" % lib_path, local_path]
        elif self.is_installed():
            executable = [self.executable]
        else:
            executable = ""
        return executable

    def is_installed(self):
        installed = os.path.exists(os.path.join(SNES9X_RUNNER_DIR,
                                                self.executable))
        if not installed:
            installed = super(snes9x, self).is_installed()
        return installed

    def set_option(self, option, value):
        config_file = os.path.join(os.path.expanduser("~"),
                                   ".snes9x/snes9x.xml")
        if not os.path.exists(config_file):
            logger.debug("Creating new config file")
            subprocess.Popen(" ".join(self.get_executable()) + " -help",
                             shell=True)
        tree = etree.parse(config_file)
        node = tree.find("./preferences/option[@name='%s']" % option)
        if value.__class__.__name__ == "bool":
            value = "1" if value else "0"
        node.attrib['value'] = value
        tree.write(config_file)

    def install(self):
        """ Install snes9x from lutris.net """
        logger.debug("Installing snes9x")
        arch = platform.architecture()[0]
        tarball_url = SNES9X_64 if arch == '64bit' else SNES9X_32
        tarball_file = os.path.basename(tarball_url)
        dest = os.path.join(settings.TMP_PATH, tarball_file)
        logger.debug("Downloading %s" % tarball_url)
        urllib.urlretrieve(tarball_url, dest)

        logger.debug("Extracting %s" % dest)
        extract_archive(dest, RUNNER_DIR)

        lib_dir = os.path.join(SNES9X_RUNNER_DIR, "lib")
        os.mkdir(lib_dir)
        libpng_url = LIBPNG_64 if arch == '64bit' else LIBPNG_32
        libpng_file = os.path.basename(libpng_url)
        lib_abspath = os.path.join(lib_dir, libpng_file)
        logger.debug("Downloading %s" % libpng_url)
        urllib.urlretrieve(libpng_url, lib_abspath)
        logger.debug("Extracting %s" % lib_abspath)
        lib_abspath = decompress_gz(lib_abspath)
        logger.debug("Creating lib symlinks")
        os.link(lib_abspath, lib_abspath[:-5])
        os.link(lib_abspath, lib_abspath[:-8])
