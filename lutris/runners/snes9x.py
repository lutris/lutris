# -*- coding:Utf-8 -*-
""" Super Nintendo runner """
import os
import urllib
import platform

from lutris.runners.runner import Runner
from lutris.constants import TMP_PATH, LUTRIS_DATA_PATH
from lutris.util.extract import extract_archive, decompress_gz

SNES9X_VERSION = "snes9x-1.53"
SNES9X_32 = "http://lutris.net/files/runners/%s-gtk-81-i386.tar.bz2" \
    % SNES9X_VERSION
SNES9X_64 = "http://lutris.net/files/runners/%s-gtk-81-x86_64.tar.bz2" \
    % SNES9X_VERSION
LIBPNG_32 = NotImplemented
LIBPNG_64 = "http://lutris.net/files/lib64/libpng14.so.14.12.0.gz"

RUNNER_DIR = os.path.join(LUTRIS_DATA_PATH, "runners/")
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
        self.machine = "Super Nintendo"
        self.is_installable = True
        self.game_options = [{"option": "rom",
                              "type": "file_chooser",
                              "default_path": "game_path",
                              "label": "ROM"}]
        self.runner_options = [{"option": "fullscreen",
                                "type": "bool",
                                "label": "Fullscreen"}]
        if settings:
            self.rom = settings["game"]["rom"]

    def play(self):
        """Run Super Nintendo game"""
        return self.get_executable() + ["\"%s\"" % self.rom]

    def get_executable(self):
        local_path = os.path.join(SNES9X_RUNNER_DIR, self.executable)
        lib_path = os.path.join(SNES9X_RUNNER_DIR, "lib")
        if os.path.exists(local_path):
            executable = ["LD_LIBRARY_PATH=\"%s\"" % lib_path, local_path]
        else:
            executable = [self.executable]
        return executable

    def is_installed(self):
        installed = os.path.exists(os.path.join(SNES9X_RUNNER_DIR,
                                                self.executable))
        if not installed:
            installed = super(snes9x, self).is_installed()
        return installed

    def install(self):
        arch = platform.architecture()[0]
        tarball_url = SNES9X_64 if arch == '64bit' else SNES9X_32
        tarball_file = os.path.basename(tarball_url)
        dest = os.path.join(TMP_PATH, tarball_file)
        urllib.urlretrieve(tarball_url, dest)
        extract_archive(dest, RUNNER_DIR)

        lib_dir = os.path.join(SNES9X_RUNNER_DIR, "lib")
        os.mkdir(lib_dir)
        libpng_url = LIBPNG_64 if arch == '64bit' else LIBPNG_32
        libpng_file = os.path.basename(libpng_url)
        lib_abspath = os.path.join(lib_dir, libpng_file)
        urllib.urlretrieve(libpng_url, lib_abspath)
        lib_abspath = decompress_gz(lib_abspath)
        os.link(lib_abspath, lib_abspath[:-5])
        os.link(lib_abspath, lib_abspath[:-8])
