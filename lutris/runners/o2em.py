# Standard Library
import os
from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class o2em(Runner):
    human_name = _("O2EM")
    description = _("Magnavox Odyssey² Emulator")
    platforms = (
        _("Magnavox Odyssey²"),
        _("Phillips C52"),
        _("Phillips Videopac+"),
        _("Brandt Jopac"),
    )
    bios_path = os.path.expanduser("~/.o2em/bios")
    runner_executable = "o2em/o2em"

    checksums = {
        "o2rom": "562d5ebf9e030a40d6fabfc2f33139fd",
        "c52": "f1071cdb0b6b10dde94d3bc8a6146387",
        "jopac": "279008e4a0db2dc5f1c048853b033828",
        "g7400": "79008e4a0db2dc5f1c048853b033828",
    }

    bios_choices = [
        (_("Magnavox Odyssey²"), "o2rom"),
        (_("Phillips C52"), "c52"),
        (_("Phillips Videopac+"), "g7400"),
        (_("Brandt Jopac"), "jopac"),
    ]
    controller_choices = [
        (_("Disable"), "0"),
        (_("Arrow Keys and Right Shift"), "1"),
        (_("W,S,A,D,SPACE"), "2"),
        (_("Joystick"), "3"),
    ]
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "default_path": "game_path",
            "help": _("The game data, commonly called a ROM image."),
        }
    ]
    runner_options = [
        {
            "option": "bios",
            "type": "choice",
            "choices": bios_choices,
            "label": _("BIOS"),
            "default": "o2rom",
        },
        {
            "option": "controller1",
            "type": "choice",
            "choices": controller_choices,
            "section": _("Controllers"),
            "label": _("First controller"),
            "default": "2",
        },
        {
            "option": "controller2",
            "type": "choice",
            "choices": controller_choices,
            "section": _("Controllers"),
            "label": _("Second controller"),
            "default": "1",
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Fullscreen"),
            "default": False,
        },
        {
            "option": "scanlines",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Scanlines display style"),
            "default": False,
            "help": _("Activates a display filter adding scanlines to imitate the displays of yesteryear."),
        },
    ]

    def get_platform(self):
        bios = self.runner_config.get("bios")
        if bios:
            for i, b in enumerate(self.bios_choices):
                if b[1] == bios:
                    return self.platforms[i]
        return ""

    def install(self, install_ui_delegate, version=None, callback=None):
        def on_runner_installed(*args):
            if not system.path_exists(self.bios_path):
                os.makedirs(self.bios_path)
            if callback:
                callback()

        super().install(install_ui_delegate, version, on_runner_installed)

    def play(self):
        arguments = ["-biosdir=%s" % self.bios_path]

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")

        if self.runner_config.get("scanlines"):
            arguments.append("-scanlines")

        if "controller1" in self.runner_config:
            arguments.append("-s1=%s" % self.runner_config["controller1"])
        if "controller2" in self.runner_config:
            arguments.append("-s2=%s" % self.runner_config["controller2"])
        rom_path = self.game_config.get("main_file") or ""
        if not system.path_exists(rom_path):
            raise MissingGameExecutableError(filename=rom_path)
        romdir = os.path.dirname(rom_path)
        romfile = os.path.basename(rom_path)
        arguments.append("-romdir=%s/" % romdir)
        arguments.append(romfile)
        return {"command": self.get_command() + arguments}
