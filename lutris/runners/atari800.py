# -*- coding:Utf-8 -*-
import os.path
import logging

from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import DownloadDialog, ErrorDialog
from lutris.runners.runner import Runner
from lutris.util.extract import extract_archive
from lutris.util.system import get_md5_hash
from lutris.util.display import get_resolutions


# pylint: disable=C0103
class atari800(Runner):
    """ Runs Atari800 games """
    human_name = "Atari800"
    package = "atari800"
    executable = "atari800"
    platform = "Atari 8bit computers"
    bios_url = (
        "http://kent.dl.sourceforge.net/project/atari800/"
        "ROM/Original%20XL%20ROM/xf25.zip"
    )
    description = "Atari 400,800 and XL emulator."
    bios_checksums = {
        "xlxe_rom": "06daac977823773a3eea3422fd26a703",
        "basic_rom": "0bac0c6a50104045d902df4503a4c30b",
        "osa_rom": "",
        "osb_rom": "a3e8d617c95d08031fe1b20d541434b2",
        "5200_rom": ""
    }
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            'help': ("The game data, commonly called a ROM image. \n"
                     "Supported rom formats: ATR, XFD, DCM, ATR.GZ, XFD.GZ "
                     "and PRO.")
        }
    ]
    try:
        screen_resolutions = [(resolution, resolution)
                              for resolution in get_resolutions()]
    except OSError:
        screen_resolutions = []
    screen_resolutions.insert(0, ('Desktop resolution', 'desktop'))

    runner_options = [
        {
            "option": "bios_path",
            "type": "directory_chooser",
            "label": "Bios location",
            'help': ("A folder containing the Atari 800 bios files.\n"
                     "They are provided by Lutris so you shouldn't have to "
                     "change this.")
        },
        {
            "option": "machine",
            "type": "choice",
            "choices": [("Emulate Atari 800", "atari"),
                        ("Emulate Atari 800 XL", "xl"),
                        ("Emulate Atari 320 XE (Compy Shop)", "320xe"),
                        ("Emulate Atari 320 XE (Rambo)", "rambo"),
                        ("Emulate Atari 5200", "5200")],
            "default": "atari",
            "label": "Machine"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "default": False,
            "label": "Fullscreen"
        },
        {
            "option": "resolution",
            "type": "choice",
            "choices": screen_resolutions,
            "default": 'desktop',
            "label": "Fullscreen resolution"
        }
    ]
    tarballs = {
        "x64": "atari800-3.1.0-x86_64.tar.gz",
    }

    def install(self):
        success = super(atari800, self).install()
        if not success:
            return False
        config_path = os.path.expanduser("~/.atari800")
        if not os.path.exists(config_path):
            os.makedirs(config_path)
        bios_archive = os.path.join(config_path, 'atari800-bioses.zip')
        dlg = DownloadDialog(self.bios_url, bios_archive)
        dlg.run()
        if not os.path.exists(bios_archive):
            ErrorDialog("Could not download Atari800 BIOS archive")
            return
        extract_archive(bios_archive, config_path)
        os.remove(bios_archive)
        config = LutrisConfig(runner='atari800')
        config.runner_config = {'atari800': {'bios_path': config_path}}
        config.save()

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'atari800/bin/atari800')

    def find_good_bioses(self, bios_path):
        """ Check for correct bios files """
        good_bios = {}
        for filename in os.listdir(bios_path):
            real_hash = get_md5_hash(os.path.join(bios_path, filename))
            for bios_file in self.bios_checksums.keys():
                if real_hash == self.bios_checksums[bios_file]:
                    logging.debug("%s Checksum : OK", filename)
                    good_bios[bios_file] = filename
        return good_bios

    def play(self):
        arguments = [self.get_executable()]
        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        else:
            arguments.append("-windowed")

        if self.runner_config.get("resolution"):
            width, height = self.runner_config["resolution"].split('x')
            arguments += ["-fs-width", "%s" % width,
                          "-fs-height", "%s" % height]

        if self.runner_config.get("machine"):
            arguments.append("-%s" % self.runner_config["machine"])

        bios_path = self.runner_config.get("bios_path")
        if not os.path.exists(bios_path):
            return {'error': 'NO_BIOS'}
        good_bios = self.find_good_bioses(bios_path)
        for bios in good_bios.keys():
            arguments.append("-%s" % bios)
            arguments.append(os.path.join(bios_path, good_bios[bios]))

        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)

        return {"command": arguments}
