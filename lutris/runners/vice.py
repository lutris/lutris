# Standard Library
import os
from gettext import gettext as _

# Lutris Modules
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger


class vice(Runner):
    description = _("Commodore Emulator")
    human_name = _("Vice")
    platforms = [
        _("Commodore 64"),
        _("Commodore 128"),
        _("Commodore VIC20"),
        _("Commodore PET"),
        _("Commodore Plus/4"),
        _("Commodore CBM II"),
    ]
    machine_choices = [
        ("C64", "c64"),
        ("C128", "c128"),
        ("vic20", "vic20"),
        ("PET", "pet"),
        ("Plus/4", "plus4"),
        ("CBM-II", "cbmii"),
    ]
    game_options = [
        {
            "option":
            "main_file",
            "type":
            "file",
            "label":
            _("ROM file"),
            "help": _(
                "The game data, commonly called a ROM image.\n"
                "Supported formats: X64, D64, G64, P64, D67, D71, D81, "
                "D80, D82, D1M, D2M, D4M, T46, P00 and CRT."
            ),
        }
    ]

    runner_options = [
        {
            "option": "joy",
            "type": "bool",
            "label": _("Use joysticks"),
            "default": False
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": False,
        },
        {
            "option": "double",
            "type": "bool",
            "label": _("Scale up display by 2"),
            "default": True,
        },
        {
            "option": "aspect_ratio",
            "type": "bool",
            "label": _("Preserve aspect ratio"),
            "default": True,
        },
        {
            "option": "drivesound",
            "type": "bool",
            "label": _("Enable sound emulation of disk drives"),
            "default": False,
        },
        {
            "option": "renderer",
            "type": "choice",
            "label": _("Graphics renderer"),
            "choices": [("OpenGL", "opengl"), (_("Software"), "software")],
            "default": "opengl",
        },
        {
            "option": "machine",
            "type": "choice",
            "label": _("Machine"),
            "choices": machine_choices,
            "default": "c64",
        },
    ]

    def get_platform(self):
        machine = self.game_config.get("machine")
        if machine:
            for index, choice in enumerate(self.machine_choices):
                if choice[1] == machine:
                    return self.platforms[index]
        return self.platforms[0]  # Default to C64

    def get_executable(self, machine=None):
        if not machine:
            machine = "c64"
        executables = {
            "c64": "x64",
            "c128": "x128",
            "vic20": "xvic",
            "pet": "xpet",
            "plus4": "xplus4",
            "cbmii": "xcbm2",
        }
        try:
            executable = executables[machine]
        except KeyError:
            raise ValueError("Invalid machine '%s'" % machine)
        return os.path.join(settings.RUNNER_DIR, "vice/bin/%s" % executable)

    def install(self, version=None, downloader=None, callback=None):

        def on_runner_installed(*args):
            config_path = system.create_folder("~/.vice")
            lib_dir = os.path.join(settings.RUNNER_DIR, "vice/lib/vice")
            if not system.path_exists(lib_dir):
                lib_dir = os.path.join(settings.RUNNER_DIR, "vice/lib64/vice")
            if not system.path_exists(lib_dir):
                logger.error("Missing lib folder in the Vice runner")
            else:
                system.merge_folders(lib_dir, config_path)
            if callback:
                callback()

        super(vice, self).install(version, downloader, on_runner_installed)

    def get_roms_path(self, machine=None):
        if not machine:
            machine = "c64"
        paths = {
            "c64": "C64",
            "c128": "C128",
            "vic20": "VIC20",
            "pet": "PET",
            "plus4": "PLUS4",
            "cmbii": "CBM-II",
        }
        root_dir = os.path.dirname(os.path.dirname(self.get_executable()))
        return os.path.join(root_dir, "lib64/vice", paths[machine])

    @staticmethod
    def get_option_prefix(machine):
        prefixes = {
            "c64": "VICII",
            "c128": "VICII",
            "vic20": "VIC",
            "pet": "CRTC",
            "plus4": "TED",
            "cmbii": "CRTC",
        }
        return prefixes[machine]

    @staticmethod
    def get_joydevs(machine):
        joydevs = {"c64": 2, "c128": 2, "vic20": 1, "pet": 0, "plus4": 2, "cmbii": 0}
        return joydevs[machine]

    @staticmethod
    def get_rom_args(machine, rom):
        args = []

        if rom.endswith(".crt"):
            crt_option = {
                "c64": "-cartcrt",
                "c128": "-cartcrt",
                "vic20": "-cartgeneric",
                "pet": None,
                "plus4": "-cart",
                "cmbii": None,
            }
            if crt_option[machine]:
                args.append(crt_option[machine])

        args.append(rom)
        return args

    def play(self):
        machine = self.runner_config.get("machine")

        rom = self.game_config.get("main_file")
        if not rom:
            return {"error": "CUSTOM", "text": "No rom provided"}
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}

        params = [self.get_executable(machine)]
        rom_dir = os.path.dirname(rom)
        params.append("-chdir")
        params.append(rom_dir)
        option_prefix = self.get_option_prefix(machine)

        if self.runner_config.get("fullscreen"):
            params.append("-{}full".format(option_prefix))

        if self.runner_config.get("double"):
            params.append("-{}dsize".format(option_prefix))

        if self.runner_config.get("renderer"):
            params.append("-sdl2renderer")
            params.append(self.runner_config["renderer"])

        if not self.runner_config.get("aspect_ratio", True):
            params.append("-sdlaspectmode")
            params.append("0")

        if self.runner_config.get("drivesound"):
            params.append("-drivesound")

        if self.runner_config.get("joy"):
            for dev in range(self.get_joydevs(machine)):
                params += ["-joydev{}".format(dev + 1), "4"]

        params.extend(self.get_rom_args(machine, rom))
        return {"command": params}
