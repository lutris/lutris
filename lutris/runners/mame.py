"""Runner for MAME"""

import os
from gettext import gettext as _

from lutris import runtime, settings
from lutris.exceptions import GameConfigError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.mame.database import get_supported_systems
from lutris.util.strings import split_arguments

MAME_CACHE_DIR = os.path.join(settings.CACHE_DIR, "mame")
MAME_XML_PATH = os.path.join(MAME_CACHE_DIR, "mame.xml")


def write_mame_xml(force=False):
    if not system.path_exists(MAME_CACHE_DIR):
        system.create_folder(MAME_CACHE_DIR)
    if system.path_exists(MAME_XML_PATH, exclude_empty=True) and not force:
        return False
    logger.info("Writing full game list from MAME to %s", MAME_XML_PATH)
    mame_inst = mame()
    mame_inst.write_xml_list()
    if system.get_disk_size(MAME_XML_PATH) == 0:
        logger.warning("MAME did not write anything to %s", MAME_XML_PATH)
        return False
    return True


def notify_mame_xml(result, error):
    if error:
        logger.error("Failed writing MAME XML")
    elif result:
        logger.info("Finished writing MAME XML")


def get_system_choices(include_year=True):
    """Return list of systems for inclusion in dropdown"""
    if not system.path_exists(MAME_XML_PATH, exclude_empty=True):
        mame_inst = mame()
        if mame_inst.is_installed():
            AsyncCall(write_mame_xml, notify_mame_xml)
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
    flatpak_id = "org.mamedev.MAME"
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
        },
        {
            "option": "machine",
            "type": "choice_with_search",
            "label": _("Machine"),
            "choices": get_system_choices,
            "help": _("The emulated machine."),
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
                (_("CD-ROM"), "cdrm"),
                (_("CD-ROM 1"), "cdrm1"),
                (_("CD-ROM 2"), "cdrm2"),
                (_("Snapshot (dump)"), "dump"),
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
            "option": "slots",
            "type": "string",
            "label": ("Slot System"),
            "help": ("For slot devices that is needed for romsloads"),
        },
        {
            "option": "autoboot_command",
            "type": "string",
            "section": _("Autoboot"),
            "label": _("Autoboot command"),
            "help": _(
                "Autotype this command when the system has started, " "an enter keypress is automatically added."
            ),
        },
        {
            "option": "autoboot_delay",
            "type": "range",
            "section": _("Autoboot"),
            "label": _("Delay before entering autoboot command"),
            "min": 0,
            "max": 120,
        },
    ]

    runner_options = [
        {
            "option": "rompath",
            "type": "directory",
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
            "section": _("Graphics"),
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "crt",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("CRT effect ()"),
            "help": _("Applies a CRT effect to the screen." "Requires OpenGL renderer."),
            "default": False,
        },
        {
            "option": "verbose",
            "type": "bool",
            "section": _("Debugging"),
            "label": _("Verbose"),
            "help": _("display additional diagnostic information."),
            "default": False,
            "advanced": True,
        },
        {
            "option": "log",
            "type": "bool",
            "section": _("Debugging"),
            "label": _("Log"),
            "help": _("generate an error.log file."),
            "default": False,
            "advanced": True,
        },
        {
            "option": "oslog",
            "type": "bool",
            "section": _("Debugging"),
            "label": _("OSLog"),
            "help": _("output error.log data to system diagnostic output (debugger or standard error)"),
            "default": False,
            "advanced": True,
        },
        {
            "option": "video",
            "type": "choice",
            "section": _("Graphics"),
            "label": _("Video backend"),
            "choices": (
                (_("Auto"), ""),
                ("OpenGL", "opengl"),
                ("BGFX", "bgfx"),
                ("SDL2", "accel"),
                (_("Software"), "soft"),
            ),
            "default": "opengl",
        },
        {
            "option": "waitvsync",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Wait for VSync"),
            "help": _(
                "Enable waiting for  the  start  of  vblank  before " "flipping  screens; reduces tearing effects."
            ),
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
            "help": _("Key to switch between Full Keyboard Mode and " "Partial Keyboard Mode (default: Scroll Lock)"),
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

    def install(self, install_ui_delegate, version=None, callback=None):
        def on_runner_installed(*args):
            def on_mame_ready(result, error):
                notify_mame_xml(result, error)
                if callback:
                    callback(*args)

            AsyncCall(write_mame_xml, on_mame_ready)

        super().install(install_ui_delegate, version=version, callback=on_runner_installed)

    @property
    def default_path(self):
        """Return the default path, use the runner's rompath"""
        main_file = self.game_config.get("main_file")
        if main_file:
            return os.path.dirname(main_file)
        return self.runner_config.get("rompath")

    def write_xml_list(self):
        """Write the full game list in XML to disk"""
        env = runtime.get_env()
        listxml_command = self.get_command() + ["-listxml"]
        os.makedirs(self.cache_dir, exist_ok=True)
        output, error_output = system.execute_with_error(listxml_command, env=env)
        if output:
            with open(self.xml_path, "w", encoding="utf-8") as xml_file:
                xml_file.write(output)
            logger.info("MAME XML list written to %s", self.xml_path)
        else:
            logger.warning("Couldn't get any output for mame -listxml: %s", error_output)

    def get_platform(self):
        selected_platform = self.game_config.get("platform")
        if selected_platform:
            return self.platforms[int(selected_platform)]
        if self.game_config.get("machine"):
            machine_mapping = {choice[1]: choice[0] for choice in get_system_choices(include_year=False)}
            # get_system_choices() can return [] if not yet ready, so we'll return
            # None in that case.
            return machine_mapping.get(self.game_config["machine"])
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
            system.execute(
                self.get_command() + ["-createconfig", "-inipath", self.config_dir],
                env=runtime.get_env(),
                cwd=self.working_dir,
            )

    def get_shader_params(self, shader_dir, shaders):
        """Returns a list of CLI parameters to apply a list of shaders"""
        params = []
        shader_path = os.path.join(self.working_dir, "shaders", shader_dir)
        for index, shader in enumerate(shaders):
            params += ["-gl_glsl", "-glsl_shader_mame%s" % index, os.path.join(shader_path, shader)]
        return params

    def play(self):
        command = self.get_command() + ["-skip_gameinfo", "-inipath", self.config_dir]
        if self.runner_config.get("video"):
            command += ["-video", self.runner_config["video"]]
        if not self.runner_config.get("fullscreen"):
            command.append("-window")
        if self.runner_config.get("waitvsync"):
            command.append("-waitvsync")
        if self.runner_config.get("uimodekey"):
            command += ["-uimodekey", self.runner_config["uimodekey"]]

        if self.runner_config.get("crt"):
            command += self.get_shader_params("CRT-geom", ["Gaussx", "Gaussy", "CRT-geom-halation"])
            command += ["-nounevenstretch"]

        if self.runner_config.get("verbose"):
            command += ["-verbose"]
        if self.runner_config.get("log"):
            command += ["-log"]
        if self.runner_config.get("verbose"):
            command += ["-oslog"]

        if self.game_config.get("machine"):
            rompath = self.runner_config.get("rompath")
            if rompath:
                command += ["-rompath", rompath]
            command.append(self.game_config["machine"])
            for slot_arg in split_arguments(self.game_config.get("slots")):
                command.append(slot_arg)
            device = self.game_config.get("device")
            if not device:
                raise GameConfigError(_("No device is set for machine %s") % self.game_config["machine"])
            rom = self.game_config.get("main_file")
            if rom:
                command += ["-" + device, rom]
        else:
            rompath = os.path.dirname(self.game_config.get("main_file"))
            if not rompath:
                rompath = self.runner_config.get("rompath")
            rom = os.path.basename(self.game_config.get("main_file"))
            if not rompath:
                raise GameConfigError(_("The path '%s' is not set. please set it in the options.") % "rompath")
            command += ["-rompath", rompath, rom]

        if self.game_config.get("autoboot_command"):
            command += ["-autoboot_command", self.game_config["autoboot_command"] + "\\n"]
            if self.game_config.get("autoboot_delay"):
                command += ["-autoboot_delay", str(self.game_config["autoboot_delay"])]

        for arg in split_arguments(self.game_config.get("args")):
            command.append(arg)

        return {"command": command}
