"""Runner for MAME"""
# Standard Library
import os
import subprocess
from gettext import gettext as _

# Lutris Modules
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger
from lutris.util.mame.database import get_supported_systems


def get_system_choices(include_year=True):
    """Return list of systems for inclusion in dropdown"""
    xml_path = os.path.join(settings.CACHE_DIR, "mame", "mame.xml")
    if not system.path_exists(xml_path):
        logger.info("Getting full game list from MAME...")
        mame_inst = mame()
        mame_inst.write_xml_list()
    for system_id, info in sorted(
        get_supported_systems(xml_path).items(),
        key=lambda sys: (sys[1]["manufacturer"], sys[1]["description"]),
    ):
        if info["description"].startswith(info["manufacturer"]):
            template = ""
        else:
            template = "%(manufacturer)s "
        template += "%(description)s"
        if include_year:
            template += " %(year)s"
        yield (template % info, system_id)


class mame(Runner):  # pylint: disable=invalid-name

    """MAME runner"""

    human_name = _("MAME")
    description = _("Arcade game emulator")
    platforms = [_("Arcade"), _("Plug & Play TV games"), _("LCD handheld games"), _("Game & Watch")]
    runner_executable = "mame/mame"
    runnable_alone = True
    config_dir = os.path.expanduser("~/.mame")
    cache_dir = os.path.join(settings.CACHE_DIR, "mame")
    xml_path = os.path.join(cache_dir, "mame.xml")

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "default_path": "game_path",
        }, {
            "option": "machine",
            "type": "choice_with_search",
            "label": _("Machine"),
            "choices": get_system_choices,
            "help": _("The emulated machine.")
        }, {
            "option":
            "device",
            "type":
            "choice_with_entry",
            "label":
            _("Storage type"),
            "choices": [
                (_("Floppy disk"), "flop"),
                (_("Floppy drive 1"), "flop1"),
                (_("Floppy drive 2"), "flop2"),
                (_("Floppy drive 3"), "flop3"),
                (_("Floppy drive 4"), "flop4"),
                (_("Cassette (tape)"), "cass"),
                (_("Cassette 1 (tape)"), "cass1"),
                (_("Cassette 2 (tape)"), "cass2"),
                (_("Cartridge"), "cart"),
                (_("Cartridge 1"), "cart1"),
                (_("Cartridge 2"), "cart2"),
                (_("Cartridge 3"), "cart3"),
                (_("Cartridge 4"), "cart4"),
                (_("Snapshot"), "snapshot"),
                (_("Hard Disk"), "hard"),
                (_("Hard Disk 1"), "hard1"),
                (_("Hard Disk 2"), "hard2"),
                (_("CDROM"), "cdrm"),
                (_("CDROM 1"), "cdrm1"),
                (_("CDROM 2"), "cdrm2"),
                (_("Snapshot"), "dump"),
                (_("Quickload"), "quickload"),
                (_("Memory Card"), "memc"),
                (_("Cylinder"), "cyln"),
                (_("Punch Tape 1"), "ptap1"),
                (_("Punch Tape 2"), "ptap2"),
                (_("Print Out"), "prin"),
            ],
        }, {
            "option": "platform",
            "type": "choice",
            "label": _("Platform"),
            "choices": ((_("Auto"), ""), (_("Plug & Play TV games"), "1"), (_("LCD handheld games"), "2")),
        }, {
            "option": "autoboot_command",
            "type": "string",
            "label": _("Autoboot command"),
            "help": _("Autotype this command when the system has started,"
                      "an enter keypress is automatically added."),
        }, {
            "option": "autoboot_delay",
            "type": "range",
            "label": _("Delay before entering autoboot command"),
            "min": 0,
            "max": 120,
        }
    ]

    runner_options = [
        {
            "option":
            "rompath",
            "type":
            "directory_chooser",
            "label":
            _("ROM/BIOS path"),
            "help": _(
                "Choose the folder containing ROMs and BIOS files.\n"
                "These files contain code from the original hardware "
                "necessary to the emulation."
            ),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "video",
            "type": "choice",
            "label": _("Video backend"),
            "choices": (
                (_("Auto"), ""),
                ("OpenGL", "opengl"),
                ("BGFX", "bgfx"),
                ("SDL2", "accel"),
                (_("Software"), "soft"),
            ),
            "default": "",
        },
        {
            "option": "waitvsync",
            "type": "bool",
            "label": _("Wait for VSync"),
            "help":
            _("Enable waiting for  the  start  of  VBLANK  before "
              "flipping  screens; reduces tearing effects."),
            "advanced": True,
            "default": False,
        },
        {
            "option":
            "uimodekey",
            "type":
            "choice_with_entry",
            "label":
            _("Menu mode key"),
            "choices": [
                (_("Scroll Lock"), "SCRLOCK"),
                (_("Num Lock"), "NUMLOCK"),
                (_("Caps Lock"), "CAPSLOCK"),
                (_("Menu"), "MENU"),
                (_("Right Control"), "RCONTROL"),
                (_("Left Control"), "LCONTROL"),
                (_("Right Alt"), "RALT"),
                (_("Left Alt"), "LALT"),
                (_("Right Super"), "RWIN"),
                (_("Left Super"), "LWIN"),
            ],
            "default":
            "SCRLOCK",
            "advanced":
            True,
            "help": _("Key to switch between Full Keyboard Mode and "
                      "Partial Keyboard Mode (default: Scroll Lock)"),
        },
    ]

    @property
    def working_dir(self):
        return os.path.join(settings.RUNNER_DIR, "mame")

    def write_xml_list(self):
        """Write the full game list in XML to disk"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        with open(self.xml_path, "w") as xml_file:
            output = system.execute([self.get_executable(), "-listxml"])
            xml_file.write(output)
            logger.info("MAME XML list written to %s", self.xml_path)

    def get_platform(self):
        selected_platform = self.game_config.get("platform")
        if selected_platform:
            return self.platforms[int(selected_platform)]
        if self.game_config.get("machine"):
            machine_mapping = {choice[1]: choice[0] for choice in get_system_choices(include_year=False)}
            return machine_mapping[self.game_config["machine"]]
        rom_file = os.path.basename(self.game_config.get("main_file", ""))
        if rom_file.startswith("gnw_"):
            return _("Nintendo Game & Watch")
        return _("Arcade")

    def prelaunch(self):
        if not system.path_exists(os.path.join(self.config_dir, "mame.ini")):
            try:
                os.makedirs(self.config_dir)
            except OSError:
                pass
            subprocess.Popen(
                [self.get_executable(), "-createconfig", "-inipath", self.config_dir],
                stdout=subprocess.PIPE,
                cwd=self.working_dir
            )
        return True

    def play(self):
        command = [self.get_executable(), "-skip_gameinfo", "-inipath", self.config_dir]
        if self.runner_config.get("video"):
            command += ["-video", self.runner_config["video"]]
        if not self.runner_config.get("fullscreen"):
            command.append("-window")
        if self.runner_config.get("waitvsync"):
            command.append("-waitvsync")
        if self.runner_config.get("uimodekey"):
            command += ["-uimodekey", self.runner_config["uimodekey"]]

        if self.game_config.get("machine"):
            rompath = self.runner_config.get("rompath")
            if rompath:
                command += ["-rompath", rompath]
            command.append(self.game_config["machine"])
            device = self.game_config["device"]
            rom = self.game_config["main_file"]
            command += ["-" + device, rom]
        else:
            rompath = os.path.dirname(self.game_config.get("main_file"))
            if rompath:
                command += ["-rompath", rompath]
            rom = os.path.basename(self.game_config.get("main_file"))
            command += [rom]

        if self.game_config.get("autoboot_command"):
            command += ["-autoboot_command", self.game_config["autoboot_command"] + "\\n"]
            if self.game_config.get("autoboot_delay"):
                command += ["-autoboot_delay", str(self.game_config["autoboot_delay"])]

        return {"command": command}
