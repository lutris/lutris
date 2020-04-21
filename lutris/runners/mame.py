"""Runner for MAME"""
import os
import subprocess
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger

from lutris.util.mame.database import get_supported_systems


def get_system_choices():
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
            yield ("%(description)s (%(year)s)" % info, system_id)
        else:
            yield ("%(manufacturer)s %(description)s (%(year)s)" % info, system_id)


class mame(Runner):
    """MAME runner"""

    human_name = "MAME"
    description = "Arcade game emulator"
    platforms = ["Arcade", "Plug & Play TV games", "LCD handheld games", "Game & Watch"]
    runner_executable = "mame/mame"
    runnable_alone = True
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
            "help": "The emulated machine.",
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
                ("Arcade", "0"),
                ("Plug & Play TV games", "1"),
                ("LCD handheld games", "2"),
                ("Game & Watch", "3"),
            ),
        },
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": True,
        },
        {
            "option": "video",
            "type": "choice",
            "choices": (
                ("Auto (Default)", ""),
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
    @staticmethod
    def config_dir():
        """Directory where MAME configuration is located"""
        return os.path.expanduser("~/.mame")

    @property
    def cache_dir(self):
        """Directory to store data extracted from MAME"""
        return os.path.join(settings.CACHE_DIR, "mame")

    @property
    def xml_path(self):
        return os.path.join(self.cache_dir, "mame.xml")

    @property
    def working_dir(self):
        return self.config_dir

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
        return "Arcade"

    def prelaunch(self):
        if not system.path_exists(os.path.join(self.config_dir, "mame.ini")):
            try:
                os.makedirs(self.config_dir)
            except OSError:
                pass
            subprocess.Popen(
                [self.get_executable(), "-createconfig"], stdout=subprocess.PIPE
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
            device = self.game_config["device"]
            rom = self.game_config["main_file"]
            command += ["-rompath", rompath, "-" + device, rom]
        else:
            rompath = os.path.dirname(self.game_config.get("main_file"))
            rom = os.path.basename(self.game_config.get("main_file"))
            command += ["-rompath", rompath, rom]

        return {"command": command}
