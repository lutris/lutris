# -*- coding:Utf-8 -*-
""" Super Nintendo runner """
import os
import urllib
import subprocess
import xml.etree.ElementTree as etree

from lutris.util.log import logger
from lutris.runners.runner import Runner
from lutris import settings
from lutris.util.extract import extract_archive, decompress_gz

SNES9X_VERSION = "snes9x-1.53"
SNES9X_32 = settings.RUNNERS_URL + "%s-gtk-81-i386.tar.bz2" % SNES9X_VERSION
SNES9X_64 = settings.RUNNERS_URL + "%s-gtk-81-x86_64.tar.bz2" % SNES9X_VERSION
LIBPNG_32 = settings.LIB32_URL + "libpng14.so.14.12.0.gz"
LIBPNG_64 = settings.LIB64_URL + "libpng14.so.14.12.0.gz"

SNES9X_DIR = os.path.join(settings.DATA_DIR, "runners/snes9x")


class snes9x(Runner):
    """Runs Super Nintendo games with Snes9x"""

    executable = "snes9x-gtk"
    package = None
    platform = "Super Nintendo"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ROM file",
            'help': ("The game data, commonly called a ROM image.")
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": "1"
        },
        {
            "option": "maintain_aspect_ratio",
            "type": "bool",
            "label": "Maintain aspect ratio (4:3)",
            "default": "1",
            'help': ("Super Nintendo games were made for 4:3 "
                     "screens with rectangular pixels, but modern screens "
                     "have square pixels, which results in a vertically "
                     "squeezed image. This option corrects this by displaying "
                     "rectangular pixels.")
        },
        {
            "option": "sound_driver",
            "type": "choice",
            "label": "Sound driver",
            "choices": (("OSS", "0"), ("SDL", "1"), ("ALSA", "2")),
            "default": "1"
        }
    ]

    def get_executable(self):
        return os.path.join(SNES9X_DIR, self.executable)

    def is_installed(self):
        if os.path.exists(os.path.join(SNES9X_DIR, self.executable)):
            return True
        else:
            return super(snes9x, self).is_installed()

    def set_option(self, option, value):
        config_file = os.path.expanduser("~/.snes9x/snes9x.xml")
        lib_path = os.path.join(SNES9X_DIR, "lib")
        if not os.path.exists(config_file):
            subprocess.Popen(
                "LD_LIBRARY_PATH=%s \"%s\" -help " % (
                    lib_path, self.get_executable()
                ), shell=True
            )
        if not os.path.exists(config_file):
            logger.error("Snes9x config file creation failed")
            return
        tree = etree.parse(config_file)
        node = tree.find("./preferences/option[@name='%s']" % option)
        if value.__class__.__name__ == "bool":
            value = "1" if value else "0"
        node.attrib['value'] = value
        tree.write(config_file)

    def install(self):
        """ Install snes9x from lutris.net """
        logger.debug("Installing snes9x")
        tarball_url = SNES9X_64 if self.arch == 'x64' else SNES9X_32
        tarball_file = os.path.basename(tarball_url)
        dest = os.path.join(settings.TMP_PATH, tarball_file)
        logger.debug("Downloading %s" % tarball_url)
        urllib.urlretrieve(tarball_url, dest)

        logger.debug("Extracting %s" % dest)
        extract_archive(dest, SNES9X_DIR)

        lib_dir = os.path.join(SNES9X_DIR, "lib")
        os.mkdir(lib_dir)

        libpng_url = LIBPNG_64 if self.arch == 'x64' else LIBPNG_32
        libpng_file = os.path.basename(libpng_url)
        lib_abspath = os.path.join(lib_dir, libpng_file)
        logger.debug("Downloading %s" % libpng_url)
        urllib.urlretrieve(libpng_url, lib_abspath)
        logger.debug("Extracting %s" % lib_abspath)
        decompress_gz(lib_abspath)
        logger.debug("Creating lib symlinks")
        os.link(lib_abspath[:-3], lib_abspath[:-5])
        os.link(lib_abspath[:-3], lib_abspath[:-8])

    def options_as_dict(self):
        """ Return the `runner_options` class attribute as a dictionnary with
            option name as key.
        """
        option_dict = {}
        for option in self.runner_options:
            option_dict[option['option']] = option
        return option_dict

    def play(self):
        options = self.options_as_dict()
        for option_name in options:
            self.set_option(
                option_name,
                self.runner_config.get(
                    option_name, options[option_name].get('default')
                )
            )

        rom = self.settings["game"].get("main_file")
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}

        launch_info = {'command': [self.get_executable(), "\"%s\"" % rom]}

        lib_path = os.path.join(SNES9X_DIR, "lib")
        if os.path.exists(lib_path):
            launch_info['ld_library_path'] = lib_path

        return launch_info
