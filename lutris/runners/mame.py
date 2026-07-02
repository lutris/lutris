"""Runner for MAME"""

from __future__ import annotations

import os
from collections.abc import Generator
from gettext import gettext as _
from typing import Any

from lutris import runtime, settings
from lutris.exceptions import GameConfigError
from lutris.runners.runner import Runner
from lutris.util import async_choices, system
from lutris.util.log import logger
from lutris.util.mame.database import get_supported_systems
from lutris.util.strings import split_arguments


def _build_mame_systems_cache(force: bool = False) -> bool:
    """Build the MAME systems cache by generating the XML list and system JSON."""
    mame_inst = mame()
    if not mame_inst.is_installed():
        logger.warning("MAME is not installed, cannot write XML list")
        return False
    if not system.path_exists(mame.CACHE_DIR):
        system.create_folder(mame.CACHE_DIR)
    if not system.path_exists(mame.XML_PATH, exclude_empty=True) or force:
        logger.info("Writing full game list from MAME to %s", mame.XML_PATH)
        mame_inst.write_xml_list()
        if system.get_disk_size(mame.XML_PATH) == 0:
            logger.warning("MAME did not write anything to %s", mame.XML_PATH)
            return False
    if not system.path_exists(mame.SYSTEMS_PATH, exclude_empty=True) or force:
        logger.info("Building MAME systems list")
        get_supported_systems(mame.XML_PATH, force=True)
    return True


@async_choices(
    generate=_build_mame_systems_cache,
    ready=lambda: system.path_exists(mame.SYSTEMS_PATH, exclude_empty=True),
    error_message="Failed to build MAME systems cache",
)
def _get_system_choices(include_year: bool = True) -> Generator[tuple[str, str], None, None]:
    """Return list of systems for inclusion in dropdown.

    This is a module-level function to support the async_choices decorator,
    which requires callables that can be referenced at module scope.
    """
    for system_id, info in sorted(
        get_supported_systems(mame.XML_PATH).items(),
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
    SYSTEMS_PATH = os.path.join(cache_dir, "systems.json")

    CACHE_DIR = cache_dir
    XML_PATH = xml_path

    platform_dict = {
        _("Arcade"): "arcade",
    }

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
            "choices": _get_system_choices,
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
                (_("romimage1"), "rom1"),
                (_("romimage2"), "rom2"),
                (_("romimage3"), "rom3"),
                (_("romimage4"), "rom4"),
                (_("romimage5"), "rom5"),
                (_("midiin"), "min"),
                (_("midiout"), "mout"),
                (_("bitbanger"), "bitb"),
                (_("microtape1"), "utap1"),
                (_("microtape2"), "utap2"),
                (_("magtape1"), "mtap1"),
                (_("magtape2"), "mtap2"),
                (_("magtape3"), "mtap3"),
                (_("magtape4"), "mtap4"),
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
            "label": _("Slot System"),
            "help": _("For slot devices that are needed for ROM loads"),
        },
        {
            "option": "autoboot_command",
            "type": "string",
            "section": _("Autoboot"),
            "label": _("Autoboot command"),
            "help": _(
                "Autotype this command when the system has started, "
                "an enter keypress is automatically added."
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
            "label": _("CRT effect"),
            "help": _("Applies a CRT effect to the screen. Requires OpenGL renderer."),
            "default": False,
        },
        {
            "option": "verbose",
            "type": "bool",
            "section": _("Debugging"),
            "label": _("Verbose"),
            "help": _("Display additional diagnostic information."),
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
                "Enable waiting for the start of vblank before flipping screens; "
                "reduces tearing effects."
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
            "help": _(
                "Key to switch between Full Keyboard Mode and "
                "Partial Keyboard Mode (default: Scroll Lock)"
            ),
        },
    ]

    @property
    def working_dir(self) -> str:
        return os.path.join(settings.RUNNER_DIR, "mame")

    @property
    def default_path(self) -> str | None:
        """Return the default path, use the runner's rompath"""
        main_file = self.game_config.get("main_file")
        if main_file:
            return os.path.dirname(main_file)
        rompath = self.runner_config.get("rompath")
        if rompath:
            return rompath
        return super().default_path

    def write_xml_list(self) -> None:
        """Write the full game list in XML to disk"""
        env = runtime.get_env(prefer_system_libs=True)
        listxml_command = self.get_command() + ["-listxml"]
        os.makedirs(self.cache_dir, exist_ok=True)
        try:
            output, error_output = system.execute_with_error(listxml_command, env=env)
        except OSError as ex:
            logger.warning("Failed to run mame -listxml: %s", ex)
            return
        if output:
            try:
                with open(self.xml_path, "w", encoding="utf-8") as xml_file:
                    xml_file.write(output)
            except OSError as ex:
                logger.warning("Failed to write MAME XML list to %s: %s", self.xml_path, ex)
                return
            logger.info("MAME XML list written to %s", self.xml_path)
        else:
            logger.warning("Couldn't get any output for mame -listxml: %s", error_output)

    def get_platform(self) -> str:
        if self.game_config.get("machine"):
            machine_mapping = {
                choice[1]: choice[0] for choice in _get_system_choices(include_year=False)
            }
            # _get_system_choices() can return [] if not yet ready, so we'll return
            # empty string in that case.
            return machine_mapping.get(self.game_config["machine"], "")
        rom_file = os.path.basename(self.game_config.get("main_file", ""))
        if rom_file.startswith("gnw_"):
            return _("Nintendo Game & Watch")
        return self.platform_dict.get("arcade", "")

    def prelaunch(self) -> None:
        """Ensure MAME config is created before launching."""
        if not system.path_exists(os.path.join(self.config_dir, "mame.ini")):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
            except OSError as ex:
                logger.warning("Failed to create MAME config directory %s: %s", self.config_dir, ex)
                return
            system.execute(
                self.get_command() + ["-createconfig", "-inipath", self.config_dir],
                env=runtime.get_env(),
                cwd=self.working_dir,
            )

    @staticmethod
    def get_shader_params(shader_dir: str, shaders: list[str]) -> list[str]:
        """Returns a list of CLI parameters to apply a list of shaders"""
        params: list[str] = []
        shader_path = os.path.join(
            os.path.join(settings.RUNNER_DIR, "mame"), "shaders", shader_dir
        )
        for index, shader in enumerate(shaders):
            params += ["-gl_glsl", f"-glsl_shader_mame{index}", os.path.join(shader_path, shader)]
        return params

    def _get_graphics_params(self) -> list[str]:
        """Build graphics-related command-line parameters."""
        params: list[str] = []
        if self.runner_config.get("video"):
            params += ["-video", self.runner_config["video"]]
        if not self.runner_config.get("fullscreen"):
            params.append("-window")
        if self.runner_config.get("waitvsync"):
            params.append("-waitvsync")
        if self.runner_config.get("uimodekey"):
            params += ["-uimodekey", self.runner_config["uimodekey"]]
        if self.runner_config.get("crt"):
            params += self.get_shader_params("CRT-geom", ["Gaussx", "Gaussy", "CRT-geom-halation"])
            params += ["-nounevenstretch"]
        return params

    def _get_debug_params(self) -> list[str]:
        """Build debugging-related command-line parameters."""
        if self.runner_config.get("verbose"):
            return ["-verbose", "-oslog", "-log"]
        return []

    def _get_machine_params(self) -> list[str]:
        """Build command-line parameters for machine-based game configurations."""
        command: list[str] = []
        machine = self.game_config.get("machine")
        if not machine:
            return command
        rompath = self.runner_config.get("rompath")
        if rompath:
            command += ["-rompath", rompath]
        command.append(machine)
        slots = self.game_config.get("slots")
        if slots:
            for slot_arg in split_arguments(slots):
                command.append(slot_arg)
        device = self.game_config.get("device")
        if not device:
            raise GameConfigError(
                _("No device is set for machine %s") % machine
            )
        rom = self.game_config.get("main_file")
        if rom:
            command += [f"-{device}", rom]
        return command

    def _get_rom_params(self) -> list[str]:
        """Build command-line parameters for ROM-based game configurations."""
        command: list[str] = []
        rompath = os.path.dirname(self.game_config.get("main_file", ""))
        if not rompath:
            rompath = self.runner_config.get("rompath")
        rom = os.path.basename(self.game_config.get("main_file", ""))
        if not rompath:
            raise GameConfigError(
                _("The ROM path is not set. Please set it in the options.")
            )
        command += ["-rompath", rompath, rom]
        return command

    def _get_autoboot_params(self) -> list[str]:
        """Build autoboot command-line parameters."""
        command: list[str] = []
        autoboot_cmd = self.game_config.get("autoboot_command")
        if autoboot_cmd:
            command += ["-autoboot_command", autoboot_cmd + "\\n"]
            autoboot_delay = self.game_config.get("autoboot_delay")
            if autoboot_delay:
                command += ["-autoboot_delay", str(autoboot_delay)]
        return command

    def play(self) -> dict[str, Any]:
        command = self.get_command() + ["-skip_gameinfo", "-inipath", self.config_dir]
        command += self._get_graphics_params()
        command += self._get_debug_params()
        command += self._get_autoboot_params()

        if self.game_config.get("machine"):
            command += self._get_machine_params()
        else:
            command += self._get_rom_params()

        args = self.game_config.get("args")
        if args:
            for arg in split_arguments(args):
                command.append(arg)

        return {"command": command}
