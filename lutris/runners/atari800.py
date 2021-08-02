# Standard Library
import logging
import os.path
from gettext import gettext as _

# Lutris Modules
from lutris.config import LutrisConfig
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.dialogs.download import DownloadDialog
from lutris.runners.runner import Runner
from lutris.util import display, extract, system


def get_resolutions():
    try:
        screen_resolutions = [(resolution, resolution) for resolution in display.DISPLAY_MANAGER.get_resolutions()]
    except OSError:
        screen_resolutions = []
    screen_resolutions.insert(0, (_("Desktop resolution"), "desktop"))
    return screen_resolutions


# pylint: disable=C0103
class atari800(Runner):
    human_name = _("Atari800")
    platforms = [_("Atari 8bit computers")]  # FIXME try to determine the actual computer used
    runner_executable = "atari800/bin/atari800"
    bios_url = "http://kent.dl.sourceforge.net/project/atari800/ROM/Original%20XL%20ROM/xf25.zip"
    description = _("Atari 400, 800 and XL emulator")
    bios_checksums = {
        "xlxe_rom": "06daac977823773a3eea3422fd26a703",
        "basic_rom": "0bac0c6a50104045d902df4503a4c30b",
        "osa_rom": "",
        "osb_rom": "a3e8d617c95d08031fe1b20d541434b2",
        "5200_rom": "",
    }
    game_options = [
        {
            "option":
            "main_file",
            "type":
            "file",
            "label":
            _("ROM file"),
            "help": _(
                "The game data, commonly called a ROM image. \n"
                "Supported formats: ATR, XFD, DCM, ATR.GZ, XFD.GZ "
                "and PRO."
            ),
        }
    ]

    runner_options = [
        {
            "option":
            "bios_path",
            "type":
            "directory_chooser",
            "label":
            _("BIOS location"),
            "help": _(
                "A folder containing the Atari 800 BIOS files.\n"
                "They are provided by Lutris so you shouldn't have to "
                "change this."
            ),
        },
        {
            "option":
            "machine",
            "type":
            "choice",
            "choices": [
                (_("Emulate Atari 800"), "atari"),
                (_("Emulate Atari 800 XL"), "xl"),
                (_("Emulate Atari 320 XE (Compy Shop)"), "320xe"),
                (_("Emulate Atari 320 XE (Rambo)"), "rambo"),
                (_("Emulate Atari 5200"), "5200"),
            ],
            "default":
            "atari",
            "label":
            _("Machine"),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "default": False,
            "label": _("Fullscreen"),
        },
        {
            "option": "resolution",
            "type": "choice",
            "choices": get_resolutions(),
            "default": "desktop",
            "label": _("Fullscreen resolution"),
        },
    ]

    def install(self, version=None, downloader=None, callback=None):

        def on_runner_installed(*args):  # pylint: disable=unused-argument
            config_path = system.create_folder("~/.atari800")
            bios_archive = os.path.join(config_path, "atari800-bioses.zip")
            dlg = DownloadDialog(self.bios_url, bios_archive)
            dlg.run()
            if not system.path_exists(bios_archive):
                ErrorDialog(_("Could not download Atari 800 BIOS archive"))
                return
            extract.extract_archive(bios_archive, config_path)
            os.remove(bios_archive)
            config = LutrisConfig(runner_slug="atari800")
            config.raw_runner_config.update({"bios_path": config_path})
            config.save()
            if callback:
                callback()

        super(atari800, self).install(version, downloader, on_runner_installed)

    def find_good_bioses(self, bios_path):
        """ Check for correct bios files """
        good_bios = {}
        for filename in os.listdir(bios_path):
            real_hash = system.get_md5_hash(os.path.join(bios_path, filename))
            for bios_file, checksum in self.bios_checksums.items():
                if real_hash == checksum:
                    logging.debug("%s Checksum : OK", filename)
                    good_bios[bios_file] = filename
        return good_bios

    def play(self):
        arguments = [self.get_executable()]
        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        else:
            arguments.append("-windowed")

        resolution = self.runner_config.get("resolution")
        if resolution:
            if resolution == "desktop":
                width, height = display.DISPLAY_MANAGER.get_current_resolution()
            else:
                width, height = resolution.split("x")
            arguments += ["-fs-width", "%s" % width, "-fs-height", "%s" % height]

        if self.runner_config.get("machine"):
            arguments.append("-%s" % self.runner_config["machine"])

        bios_path = self.runner_config.get("bios_path")
        if not system.path_exists(bios_path):
            return {"error": "NO_BIOS"}
        good_bios = self.find_good_bioses(bios_path)
        for bios, filename in good_bios.items():
            arguments.append("-%s" % bios)
            arguments.append(os.path.join(bios_path, filename))

        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}
        arguments.append(rom)

        return {"command": arguments}
