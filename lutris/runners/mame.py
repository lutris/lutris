"""Runner for MAME"""
import os
import subprocess
from gettext import gettext as _

from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.mame.database import get_supported_systems
from lutris.util.strings import split_arguments

MAME_CACHE_DIR = os.path.join(settings.CACHE_DIR, "mame")
MAME_XML_PATH = os.path.join(MAME_CACHE_DIR, "mame.xml")


def write_mame_xml():
    if not system.path_exists(MAME_CACHE_DIR):
        system.create_folder(MAME_CACHE_DIR)
    if not system.path_exists(MAME_XML_PATH):
        logger.info("Getting full game list from MAME...")
        mame_inst = mame()
        if not mame_inst.is_installed():
            logger.info("MAME isn't installed, can't retrieve systems list.")
            return []
        mame_inst.write_xml_list()


def notify_mame_xml(*args, **kwargs):
    logger.info("MAME XML written")


def get_system_choices(include_year=True):
    """Return list of systems for inclusion in dropdown"""
    if not system.path_exists(MAME_XML_PATH, exclude_empty=True):
        AsyncCall(write_mame_xml, notify_mame_xml)
        logger.warning("MAME XML generation launched in the background, not returning anything this time")
        return []
    for system_id, info in sorted(
        get_supported_systems(MAME_XML_PATH).items(),
        key=lambda sys: (sys[1]["manufacturer"], sys[1]["description"]),
    ):
        if info["description"].startswith(info["manufacturer"]):
            template = ""
        else:
            template = "%(manufacturer)s "
        template += "%(description)s"
        if include_year:
            template += " %(year)s"
        system_name = template % info
        system_name = system_name.replace("<generic>", "").strip()
        yield (system_name, system_id)


class mame(Runner):  # pylint: disable=invalid-name

    """MAME runner"""

    human_name = _("MAME")
    description = _("Arcade game emulator")
    runner_executable = "mame/mame"
    runnable_alone = True
    config_dir = os.path.expanduser("~/.mame")
    cache_dir = os.path.join(settings.CACHE_DIR, "mame")
    xml_path = os.path.join(cache_dir, "mame.xml")
    _platforms = []

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "default_path": "game_path",
        },
        {
            "option": "machine",
            "type": "choice_with_search",
            "label": _("Machine"),
            "choices": get_system_choices,
            "help": _("The emulated machine.")
        },
        {
            "option": "device",
            "type": "choice_with_entry",
            "label": _("Storage type"),
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
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Command line arguments used when launching the game"),
        },
        {
            "option": "autoboot_command",
            "type": "string",
            "label": _("Autoboot command"),
            "help": _("Autotype this command when the system has started,"
                      "an enter keypress is automatically added."),
        },
        {
            "option": "autoboot_delay",
            "type": "range",
            "label": _("Delay before entering autoboot command"),
            "min": 0,
            "max": 120,
        }
    ]

    runner_options = [
        {
            "option": "rompath",
            "type": "directory_chooser",
            "label": _("ROM/BIOS path"),
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
            "option": "uimodekey",
            "type": "choice_with_entry",
            "label": _("Menu mode key"),
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
            "default": "SCRLOCK",
            "advanced": True,
            "help": _("Key to switch between Full Keyboard Mode and "
                      "Partial Keyboard Mode (default: Scroll Lock)"),
        },
    ]

    @property
    def working_dir(self):
        return os.path.join(settings.RUNNER_DIR, "mame")

    @property
    def platforms(self):
        if self._platforms:
            return self.platforms
        self._platforms = [choice[0] for choice in get_system_choices(include_year=False)]
        self._platforms += [_("Arcade"), _("Nintendo Game & Watch")]
        return self._platforms

    def install(self, version=None, downloader=None, callback=None):

        def on_runner_installed(*args):
            AsyncCall(write_mame_xml, notify_mame_xml)

        super().install(version=version, downloader=downloader, callback=on_runner_installed)

    def write_xml_list(self):
        """Write the full game list in XML to disk"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        with open(self.xml_path, "w") as xml_file:
            output = system.execute([self.get_executable(), "-listxml"])
            if output:
                xml_file.write(output)
            else:
                logger.warning("Couldn't get any output for mame -listxml")
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
            device = self.game_config.get("device")
            if not device:
                return {'error': "CUSTOM", "text": "No device is set for machine %s" % self.game_config["machine"]}
            rom = self.game_config["main_file"]
            command += ["-" + device, rom]
        else:
            rompath = os.path.dirname(self.game_config.get("main_file"))
            if not rompath:
                rompath = self.runner_config.get("rompath")
            rom = os.path.basename(self.game_config.get("main_file"))
            if not rompath:
                return {'error': 'PATH_NOT_SET', 'path': 'rompath'}
            command += ["-rompath", rompath, rom]

        if self.game_config.get("autoboot_command"):
            command += ["-autoboot_command", self.game_config["autoboot_command"] + "\\n"]
            if self.game_config.get("autoboot_delay"):
                command += ["-autoboot_delay", str(self.game_config["autoboot_delay"])]

        for arg in split_arguments(self.game_config.get("args")):
            command.append(arg)

        return {"command": command}
