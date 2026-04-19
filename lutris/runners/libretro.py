"""libretro runner"""

import os
from collections.abc import Iterator
from gettext import gettext as _
from operator import itemgetter
from zipfile import ZipFile

import requests

from lutris import settings
from lutris.config import LutrisConfig
from lutris.exceptions import GameConfigError, MissingBiosError, MissingGameExecutableError, UnspecifiedVersionError
from lutris.runners.runner import Runner
from lutris.util import async_choices, cache_single, system
from lutris.util.libretro import RetroConfig
from lutris.util.log import logger
from lutris.util.retroarch.firmware import get_firmware, scan_firmware_directory

RETROARCH_DIR = os.path.join(settings.RUNNER_DIR, "retroarch")

# RetroArch's own user-dir convention. System-installed cores (AUR, distro packages)
# live at distro-specific paths, so for those we rely on whatever the user has set in
# retroarch.cfg's libretro_directory / libretro_info_path rather than guessing.
USER_RETROARCH_CORES_DIR = os.path.expanduser("~/.config/retroarch/cores")
USER_RETROARCH_INFO_DIR = os.path.expanduser("~/.config/retroarch/info")

RETROARCH_TO_LUTRIS_PLATFORM_MAP = {
    "2048 Game Clone": "",
    "3D Engine": "",
    "3DO": "",
    "3DS": "Nintendo 3DS",
    "Advanced Test Core": "",
    "Amiga": "",
    "Arcade (various)": "Arcade",
    "Atari 2600": "Atari 2600",
    "Atari 5200": "",
    "Atari 7800": "",
    "Atari ST/STE/TT/Falcon": "",
    "BK-0010/BK-0011(M)": "",
    "C128": "",
    "C64": "",
    "C64 SuperCPU": "",
    "Cave Story Game Engine": "",
    "CBM-5x0": "",
    "CBM-II": "",
    "ChaiLove": "",
    "CHIP-8": "",
    "Classic Tomb Raider engine": "",
    "ColecoVision": "",
    "Commodore Amiga": "",
    "CPC": "",
    "CP System I": "",
    "CP System II": "",
    "CP System III": "",
    "Cruzes": "",
    "Dinothawr Game Engine": "",
    "Doom 3 Game Engine": "",
    "Doom 3 XP Game Engine": "",
    "DOOM Game Engine": "",
    "DOS": "",
    "DS": "",
    "FFmpeg": "",
    "Flashback Game Engine": "",
    "FreeChaF": "",
    "Game Boy Advance": "Nintendo Game Boy Advance",
    "Game Boy/Game Boy Color": "Nintendo Game Boy (Color)",
    "Game Boy/Game Boy Color/Game Boy Advance": "Nintendo Game Boy Advance",
    "GameCube / Wii": "Nintendo Wii",
    "Game engine": "",
    "Handheld Electronic": "",
    "Intellivision": "",
    "J2ME": "",
    "Jaguar": "",
    "Java ME": "",
    "LowRes NX": "",
    "Lutro": "",
    "Lynx": "",
    "Magnavox Odyssey2 / Phillips Videopac+": "",
    "Mega Duck": "",
    "Minecraft Game Clone": "",
    "Moonlight": "",
    "MPV": "",
    "Mr.Boom": "",
    "MSX": "Microsoft MSX",
    "MSX/SVI/ColecoVision/SG-1000": "",
    "Multi (various)": "",
    "Music": "",
    "Neo Geo": "",
    "Neo Geo Pocket (Color)": "SNK Neo Geo Pocket (Color)",
    "Nintendo 64": "Nintendo 64",
    "Nintendo DS": "Nintendo DS",
    "Nintendo Entertainment System": "Nintendo NES",
    "Oberon RISC machine": "",
    "Outrun Game Engine": "",
    "Palm OS": "",
    "PC": "",
    "PC-8000 / PC-8800 series": "",
    "PC-98": "",
    "PC Engine/PCE-CD": "",
    "PC Engine SuperGrafx": "",
    "PC Engine/SuperGrafx/CD": "",
    "PC-FX": "",
    "PET": "",
    "Physics Toy": "",
    "PICO8": "",
    "PlayStation": "Sony PlayStation",
    "PLUS/4": "",
    "Pokemon Mini": "",
    "Pong Game Clone": "",
    "PSP": "Sony Playstation Portable",
    "Quake 3 Game Engine": "",
    "Quake Game Engine": "",
    "Quake II Game Engine": "",
    "Redbook": "",
    "Rick Dangerous Game Engine": "",
    "RPG Maker 2000/2003 Game Engine": "",
    "SAM coupe": "",
    "Saturn": "Sega Saturn",
    "Sega 8/16-bit + 32X (Various)": "",
    "Sega 8/16-bit (Various)": "",
    "Sega 8-bit": "",
    "Sega 8-bit (MS/GG/SG-1000)": "",
    "Sega Dreamcast": "Sega Dreamcast",
    "Sega Genesis": "Sega Genesis/Mega Drive",
    "Sega Master System": "Sega Master System",
    "SEGA Visual Memory Unit": "",
    "Sharp X1": "",
    "Sharp X68000": "",
    "SNK Neo Geo CD": "",
    "Sony PlayStation 2": "",
    "Super Nintendo Entertainment System": "Nintendo SNES",
    "Super Nintendo Entertainment System / Game Boy / Game Boy Color": "",
    "Supervision": "",
    "Test for netplay": "",
    "Thomson MO/TO": "",
    "TIC-80": "",
    "Tyrian Game Engine": "",
    "Uzebox": "",
    "Vectrex": "",
    "VIC-20": "",
    "Virtual Boy": "Nintendo Virtual Boy",
    "Wolfenstein 3D Game Engine": "",
    "WonderSwan/Color": "Bandai WonderSwan Color",
    "Xbox": "",
    "ZX81": "",
    "ZX Spectrum (various)": "",
}


def get_default_config_path(path):
    return os.path.join(RETROARCH_DIR, path)


def _retroarch_config_dir(config_file: str | None, key: str) -> str | None:
    """Read a directory path from a retroarch.cfg, expanding ``~``.

    Returns None if the file is missing/unreadable, the key isn't set, or the value is
    the literal ``"default"`` (which RetroArch treats as "use the built-in default").
    """
    if not config_file or not os.path.isfile(config_file):
        return None
    try:
        value = RetroConfig(config_file).get(key)
    except OSError:
        return None
    if not value or value == "default":
        return None
    return os.path.expanduser(value)


def _info_dirs(config_file: str | None = None) -> Iterator[str]:
    """Yield existing info-file directories in priority order.

    Priority: ``libretro_info_path`` from the user's retroarch.cfg → the user's
    standalone RetroArch info dir → the Lutris-managed ``RETROARCH_DIR/info``.
    Duplicates and non-existent paths are skipped.
    """
    seen: set[str] = set()
    candidates = []
    cfg_dir = _retroarch_config_dir(config_file, "libretro_info_path")
    if cfg_dir:
        candidates.append(cfg_dir)
    candidates.append(USER_RETROARCH_INFO_DIR)
    candidates.append(os.path.join(RETROARCH_DIR, "info"))
    for path in candidates:
        if path and path not in seen and os.path.isdir(path):
            seen.add(path)
            yield path


def _download_libretro_info():
    """Download the libretro core info archive from the buildbot. Run on a worker thread."""
    info_path = os.path.join(RETROARCH_DIR, "info")
    req = requests.get("http://buildbot.libretro.com/assets/frontend/info.zip", allow_redirects=True, timeout=5)
    if req.status_code == requests.codes.ok:  # pylint: disable=no-member
        os.makedirs(RETROARCH_DIR, exist_ok=True)
        with open(os.path.join(RETROARCH_DIR, "info.zip"), "wb") as info_zip:
            info_zip.write(req.content)
        with ZipFile(os.path.join(RETROARCH_DIR, "info.zip"), "r") as info_zip:
            info_zip.extractall(info_path)
        return True
    logger.error("Error retrieving libretro info archive from server: %s - %s", req.status_code, req.reason)
    return False


@cache_single
def get_libretro_cores():
    """Return the list of available libretro cores by reading installed info files.

    Scans every info directory yielded by ``_info_dirs()`` so cores installed via the
    user's RetroArch (``~/.config/retroarch/info``) or system packages
    (e.g. ``/usr/lib/libretro/info`` on Arch/AUR) are surfaced alongside the
    Lutris-managed ones. The first occurrence of a given core identifier wins so the
    higher-priority sources (user config, then system) take precedence over the
    Lutris fallback.

    If no info directory exists anywhere, falls back to a synchronous download into
    ``RETROARCH_DIR/info``. Callers on the UI thread should prefer triggering the
    async download via ``get_core_choices()`` first, so this fallback is rarely
    reached in practice.
    """
    info_dirs = list(_info_dirs())
    if not info_dirs:
        if not _download_libretro_info():
            return []
        info_dirs = [os.path.join(RETROARCH_DIR, "info")]
    cores = []
    seen = set()
    for info_path in info_dirs:
        for info_file in os.listdir(info_path):
            if "_libretro.info" not in info_file:
                continue
            core_identifier = info_file.replace("_libretro.info", "")
            if core_identifier in seen:
                continue
            seen.add(core_identifier)
            core_config = RetroConfig(os.path.join(info_path, info_file))
            if "categories" in core_config.keys() and "Emulator" in core_config["categories"]:
                core_label = core_config["display_name"] or ""
                core_system = core_config["systemname"] or ""
                cores.append((core_label, core_identifier, core_system))
    cores.sort(key=itemgetter(0))
    return cores


@async_choices(
    generate=_download_libretro_info,
    ready=lambda: any(_info_dirs()),
    invalidate=get_libretro_cores.cache_clear,
    error_message="Failed to download libretro info archive",
)
def get_core_choices():
    """Return (label, identifier) pairs for all installed libretro cores, for use as a choices callable.

    If RetroArch is installed but the info archive hasn't been downloaded yet, kicks off a
    background download and returns [] immediately. Any callbacks registered via
    register_reload_callback() are invoked on the UI thread when the download completes, so
    dropdowns can repopulate without the user having to close and reopen the dialog.
    """
    return [(core[0], core[1]) for core in get_libretro_cores()]


class libretro(Runner):
    human_name = _("Libretro")
    description = _("Multi-system emulator")
    runnable_alone = True
    runner_executable = "retroarch/retroarch"
    flatpak_id = "org.libretro.RetroArch"

    game_options = [
        {"option": "main_file", "type": "file", "label": _("ROM file")},
        {
            "option": "core",
            "type": "choice",
            "label": _("Core"),
            "choices": get_core_choices,
        },
    ]

    runner_options = [
        {
            "option": "config_file",
            "type": "file",
            "label": _("Config file"),
            "default": os.path.join(RETROARCH_DIR, "retroarch.cfg"),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "verbose",
            "type": "bool",
            "label": _("Verbose logging"),
            "default": False,
        },
    ]

    def __init__(self, config: LutrisConfig | None = None) -> None:
        super().__init__(config)
        self.platform_dict = {}
        for core in get_libretro_cores():
            platform = core[2]
            if lutris_platform := RETROARCH_TO_LUTRIS_PLATFORM_MAP.get(platform):
                self.platform_dict[lutris_platform] = platform
            else:
                self.platform_dict[platform] = platform

    @property
    def directory(self):
        return os.path.join(settings.RUNNER_DIR, "retroarch")

    def get_platform(self):
        game_core = self.game_config.get("core")
        if not game_core:
            logger.warning("Game don't have a core set")
            return
        for core in get_libretro_cores():
            if core[1] == game_core and core[2] in self.platform_dict:
                return self.platform_dict[core[2]]
        logger.warning("'%s' not found in Libretro cores", game_core)
        return ""

    def _core_dirs(self) -> Iterator[str]:
        """Yield existing core directories in priority order.

        Mirrors ``_info_dirs()`` for the ``.so`` files: ``libretro_directory`` from
        the user's retroarch.cfg → the user's standalone RetroArch cores dir → the
        Lutris-managed ``cores`` directory.
        """
        seen: set[str] = set()
        candidates = []
        cfg_dir = _retroarch_config_dir(self.get_config_file(), "libretro_directory")
        if cfg_dir:
            candidates.append(cfg_dir)
        candidates.append(USER_RETROARCH_CORES_DIR)
        candidates.append(get_default_config_path("cores"))
        for path in candidates:
            if path and path not in seen and os.path.isdir(path):
                seen.add(path)
                yield path

    def find_core_path(self, core: str) -> str | None:
        """Return the path to an installed core ``.so``, or None if not found."""
        core_filename = "{}_libretro.so".format(core)
        for directory in self._core_dirs():
            path = os.path.join(directory, core_filename)
            if system.path_exists(path):
                return path
        return None

    def find_info_path(self, core: str) -> str | None:
        """Return the path to an installed core's ``.info`` file, or None if not found."""
        info_filename = "{}_libretro.info".format(core)
        for directory in _info_dirs(self.get_config_file()):
            path = os.path.join(directory, info_filename)
            if system.path_exists(path):
                return path
        return None

    def get_version(self, use_default=True):
        return self.game_config["core"]

    def is_installed(self, flatpak_allowed: bool = True, core=None) -> bool:
        if not core and self.has_explicit_config and self.game_config.get("core"):
            core = self.game_config["core"]
        if not core or self.runner_config.get("runner_executable"):
            return super().is_installed(flatpak_allowed=flatpak_allowed)
        is_core_installed = self.find_core_path(core) is not None
        return super().is_installed(flatpak_allowed=flatpak_allowed) and is_core_installed

    def is_installed_for(self, interpreter):
        core = interpreter.installer.script["game"].get("core")
        return self.is_installed(core=core)

    def get_installer_runner_version(self, installer, use_runner_config: bool = True) -> str:
        version = installer.script["game"].get("core")
        if not version:
            raise UnspecifiedVersionError(_("The installer does not specify the libretro 'core' version."))
        return version

    def install(self, install_ui_delegate, version=None, callback=None):
        captured_super = super()  # super() does not work inside install_core()

        def on_installed():
            get_libretro_cores.cache_clear()
            if callback:
                callback()

        def install_core():
            if not version:
                on_installed()
            else:
                captured_super.install(install_ui_delegate, version, on_installed)

        if not super().is_installed():
            captured_super.install(install_ui_delegate, version=None, callback=install_core)
        else:
            captured_super.install(install_ui_delegate, version, on_installed)

    def get_run_data(self):
        return {
            "command": self.get_command() + self.get_runner_parameters(),
            "env": self.get_env(),
        }

    def get_config_file(self):
        return self.runner_config.get("config_file") or os.path.join(RETROARCH_DIR, "retroarch.cfg")

    @staticmethod
    def get_system_directory(retro_config):
        """Return the system directory used for storing BIOS and firmwares."""
        system_directory = retro_config["system_directory"]
        if not system_directory or system_directory == "default":
            system_directory = get_default_config_path("system")
        return os.path.expanduser(system_directory)

    def prelaunch(self):
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        config_file = self.get_config_file()
        # TODO: review later
        # Create retroarch.cfg if it doesn't exist.
        if not system.path_exists(config_file):
            with open(config_file, "w", encoding="utf-8") as f:
                f.write("# Lutris RetroArch Configuration")
                f.close()

            # Build the default config settings.
            retro_config = RetroConfig(config_file)
            retro_config["libretro_directory"] = get_default_config_path("cores")
            retro_config["libretro_info_path"] = get_default_config_path("info")
            retro_config["content_database_path"] = get_default_config_path("database/rdb")
            retro_config["cheat_database_path"] = get_default_config_path("database/cht")
            retro_config["cursor_directory"] = get_default_config_path("database/cursors")
            retro_config["screenshot_directory"] = get_default_config_path("screenshots")
            retro_config["input_remapping_directory"] = get_default_config_path("remaps")
            retro_config["video_shader_dir"] = get_default_config_path("shaders")
            retro_config["core_assets_directory"] = get_default_config_path("downloads")
            retro_config["thumbnails_directory"] = get_default_config_path("thumbnails")
            retro_config["playlist_directory"] = get_default_config_path("playlists")
            retro_config["joypad_autoconfig_dir"] = get_default_config_path("autoconfig")
            retro_config["rgui_config_directory"] = get_default_config_path("config")
            retro_config["overlay_directory"] = get_default_config_path("overlay")
            retro_config["assets_directory"] = get_default_config_path("assets")
            retro_config["system_directory"] = get_default_config_path("system")
            retro_config.save()
        else:
            retro_config = RetroConfig(config_file)

        core = self.game_config.get("core")
        info_file = self.find_info_path(core) if core else None
        if info_file:
            retro_config = RetroConfig(info_file)
            try:
                firmware_count = int(retro_config["firmware_count"])
                mandatory_firmware_count = sum(
                    1 for i in range(firmware_count) if not retro_config.get("firmware%d_opt" % i)
                )
            except (ValueError, TypeError):
                firmware_count = 0
                mandatory_firmware_count = 0
            system_path = self.get_system_directory(retro_config)
            notes = str(retro_config["notes"] or "")
            checksums = {}
            if notes.startswith("(!)"):
                parts = notes.split("|")
                for part in parts:
                    try:
                        filename, checksum = part.split(" (md5): ")
                    except ValueError:
                        logger.warning("Unable to parse firmware info: %s", notes)
                        continue
                    filename = filename.replace("(!) ", "")
                    checksums[filename] = checksum

            # If this requires firmware, confirm we have the firmware folder configured in the first place
            # then rescan it in case the user added anything since the last time they changed it
            if mandatory_firmware_count > 0:
                lutris_config = LutrisConfig()
                firmware_directory = lutris_config.raw_system_config.get("bios_path")
                if not firmware_directory:
                    raise MissingBiosError(
                        _("The emulator files BIOS location must be configured in the Preferences dialog.")
                    )
                scan_firmware_directory(firmware_directory)

            for index in range(firmware_count):
                optional_prefix = "Optional firmware" if retro_config.get("firmware%d_opt" % index) else "Firmware"
                firmware_filename = retro_config["firmware%d_path" % index]
                firmware_path = os.path.join(system_path, firmware_filename)
                firmware_name = firmware_filename.split("/")[-1]
                firmware_checksum = checksums.get(firmware_name)
                if system.path_exists(firmware_path):
                    if firmware_checksum:
                        checksum = system.get_md5_hash(firmware_path)
                        if checksum == firmware_checksum:
                            checksum_status = "Checksum good"
                        else:
                            checksum_status = "Checksum failed"
                    else:
                        checksum_status = "No checksum info"
                    logger.info("%s '%s' found (%s)", optional_prefix, firmware_filename, checksum_status)
                else:
                    logger.warning("%s '%s' not found!", optional_prefix, firmware_filename)
                    if firmware_checksum:
                        get_firmware(firmware_name, firmware_checksum, system_path)

    def get_runner_parameters(self):
        parameters = []

        # Fullscreen
        fullscreen = self.runner_config.get("fullscreen")
        if fullscreen:
            parameters.append("--fullscreen")

        # Verbose
        verbose = self.runner_config.get("verbose")
        if verbose:
            parameters.append("--verbose")

        parameters.append("--config={}".format(self.get_config_file()))
        return parameters

    def play(self):
        command = self.get_command() + self.get_runner_parameters()

        # Core
        core = self.game_config.get("core")
        if not core:
            raise GameConfigError(_("No core has been selected for this game"))
        core_path = self.find_core_path(core)
        if core_path:
            command.append("--libretro={}".format(core_path))
        # If we couldn't resolve a path, fall through and let RetroArch resolve the
        # core via its own libretro_directory — covers users who manage cores entirely
        # through retroarch.cfg (e.g. AUR packages installing to /usr/lib/libretro).

        # Main file
        file = self.game_config.get("main_file")
        if not file:
            raise GameConfigError(_("No game file specified"))
        if not system.path_exists(file):
            raise MissingGameExecutableError(filename=file)
        command.append(file)
        return {"command": command}
