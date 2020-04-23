"""Runner for MAME"""
import os
import subprocess
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

    human_name = "MAME"
    description = "Arcade game emulator"
    platforms = ["Arcade", "Plug & Play TV games", "LCD handheld games", "Game & Watch"]
    runner_executable = "mame/mame"
    runnable_alone = True
    config_dir = os.path.expanduser("~/.mame")
    cache_dir = os.path.join(settings.CACHE_DIR, "mame")
    xml_path = os.path.join(cache_dir, "mame.xml")

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "default_path": "game_path",
        },
        {
            "option": "machine",
            "type": "choice_with_search",
            "label": "Machine",
            "choices": get_system_choices,
            "help": "The emulated machine."
        },
        {
            "option": "device",
            "type": "choice_with_entry",
            "label": "Storage type",
            "choices": [
                ("Floppy disk", "flop"),
                ("Floppy drive 1", "flop1"),
                ("Floppy drive 2", "flop2"),
                ("Floppy drive 3", "flop3"),
                ("Floppy drive 4", "flop4"),
                ("Cassette (tape)", "cass"),
                ("Cassette 1 (tape)", "cass1"),
                ("Cassette 2 (tape)", "cass2"),
                ("Cartridge", "cart"),
                ("Cartridge 1", "cart1"),
                ("Cartridge 2", "cart2"),
                ("Cartridge 3", "cart3"),
                ("Cartridge 4", "cart4"),
                ("Snapshot", "snapshot"),
                ("Hard Disk", "hard"),
                ("Hard Disk 1", "hard1"),
                ("Hard Disk 2", "hard2"),
                ("CDROM", "cdrm"),
                ("CDROM 1", "cdrm1"),
                ("CDROM 2", "cdrm2"),
                ("Snapshot", "dump"),
                ("Quickload", "quickload"),
                ("Memory Card", "memc"),
                ("Cylinder", "cyln"),
                ("Punch Tape 1", "ptap1"),
                ("Punch Tape 2", "ptap2"),
                ("Print Out", "prin"),
            ],
        },
        {
            "option": "platform",
            "type": "choice",
            "label": "Platform",
            "choices": (
                ("Auto", ""),
                ("Plug & Play TV games", "1"),
                ("LCD handheld games", "2")
            ),
        },
        {
            "option": "autoboot_command",
            "type": "string",
            "label": "Autoboot command",
            "help": (
                "Autotype this command when the system has started,"
                "an enter keypress is automatically added."
            ),
        },
        {
            "option": "autoboot_delay",
            "type": "range",
            "label": "Delay before entering autoboot command",
            "min": 0,
            "max": 120,
        }
    ]

    runner_options = [
        {
            "option": "rompath",
            "type": "directory_chooser",
            "label": "ROM/BIOS path",
            "help": (
                "Choose the folder containing ROMs and BIOS files.\n"
                "These files contain code from the original hardware "
                "necessary to the emulation."
            ),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": True,
        },
        {
            "option": "video",
            "type": "choice",
            "label": "Video backend",
            "choices": (
                ("Auto", ""),
                ("OpenGL", "opengl"),
                ("BGFX", "bgfx"),
                ("SDL2", "accel"),
                ("Software", "soft"),
            ),
            "default": "",
        },
        {
            "option": "waitvsync",
            "type": "bool",
            "label": "Wait for VSync",
            "help": (
                "Enable waiting for  the  start  of  VBLANK  before "
                "flipping  screens; reduces tearing effects."
            ),
            "advanced": True,
            "default": False,
        },
        {
            "option": "uimodekey",
            "type": "choice_with_entry",
            "label": "Menu mode key",
            "choices": [
                ("Scroll Lock", "SCRLOCK"),
                ("Num Lock", "NUMLOCK"),
                ("Caps Lock", "CAPSLOCK"),
                ("Menu", "MENU"),
                ("Right Control", "RCONTROL"),
                ("Left Control", "LCONTROL"),
                ("Right Alt", "RALT"),
                ("Left Alt", "LALT"),
                ("Right Super", "RWIN"),
                ("Left Super", "LWIN"),
            ],
            "default": "SCRLOCK",
            "advanced": True,
            "help": (
                "Key to switch between Full Keyboard Mode and "
                "Partial Keyboard Mode (default: Scroll Lock)"
            ),
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
            machine_mapping = {
                choice[1]: choice[0] for choice in get_system_choices(include_year=False)
            }
            return machine_mapping[self.game_config["machine"]]
        rom_file = os.path.basename(self.game_config.get("main_file", ""))
        if rom_file.startswith("gnw_"):
            return "Nintendo Game & Watch"
        return "Arcade"

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
            rom = os.path.basename(self.game_config.get("main_file"))
            command += ["-rompath", rompath, rom]

        if self.game_config.get("autoboot_command"):
            command += ["-autoboot_command", self.game_config["autoboot_command"] + "\\n"]
            if self.game_config.get("autoboot_delay"):
                command += ["-autoboot_delay", str(self.game_config["autoboot_delay"])]

        return {"command": command}
