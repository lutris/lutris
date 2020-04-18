"""libretro runner"""
import os
from lutris.runners.runner import Runner
from lutris.util.libretro import RetroConfig
from lutris.util import system
from lutris.util.log import logger
from lutris import settings

# List of supported libretro cores
# First element is the human readable name for the core with the platform's short name
# Second element is the core identifier
# Third element is the platform's long name
LIBRETRO_CORES = [
    ("atari800 (Atari 800/5200)", "atari800", "Atari 800/5200"),
    ("bsnes (Super Nintendo)", "bsnes", "Nintendo SNES"),
    ("bsnes-hd beta (Super Nintendo)", "bsnes_hd_beta", "Nintendo SNES"),
    ("BK (Elektronika BK-0010/BK-0011(M))", "bk", "Elektronika BK-0010/BK-0011"),
    ("BlastEm (Sega Genesis)", "blastem", "Sega Genesis"),
    ("blueMSX (MSX/MSX2/MSX2+)", "bluemsx", "MSX/MSX2/MSX2+"),
    ("Caprice32 (Amstrad CPC)", "cap32", "Amstrad CPC"),
    ("ChaiLove", "chailove", "ChaiLove"),
    ("Citra (Nintendo 3DS)", "citra", "Nintendo 3DS"),
    ("Citra Canary (Nintendo 3DS)", "citra_canary", "Nintendo 3DS"),
    ("CrocoDS (Amstrad CPC)", "crocods", "Amstrad CPC"),
    ("Daphne (Arcade)", "daphne", "Arcade"),
    ("DesmuME (Nintendo DS)", "desmume", "Nintendo DS"),
    ("Dinothawr (Game Engine)", "dinothawr", "Dinothawr"),
    ("Dolphin (Nintendo Wii/Gamecube)", "dolphin", "Nintendo Wii/Gamecube"),
    ("EightyOne (Sinclair ZX81)", "81", "Sinclair ZX81"),
    ("FB Alpha (Arcade)", "fbalpha", "Arcade"),
    ("FB Alpha (Capcom Play System 1)", "fbalpha2012_cps1", "Arcade"),
    ("FB Alpha (Capcom Play System 2)", "fbalpha2012_cps2", "Arcade"),
    ("FB Alpha (Capcom Play System 3)", "fbalpha2012_cps3", "Arcade"),
    ("FB Alpha (SNK Neo Geo)", "fbalpha2012_neogeo", "Arcade"),
    ("FBNeo (Arcade)", "fbneo", "Arcade"),
    ("FCEUmm (Nintendo Entertainment System)", "fceumm", "Nintendo NES"),
    ('Flycast (Sega Dreamcast)', 'flycast', 'Sega Dreamcast'),
    ("fMSX (MSX/MSX2/MSX2+)", "fmsx", "MSX/MSX2/MSX2+"),
    ("FreeJ2ME (J2ME)", "freej2me", "J2ME"),
    ("Fuse (ZX Spectrum)", "fuse", "Sinclair ZX Spectrum"),
    ("Gambatte (Game Boy Color)", "gambatte", "Nintendo Game Boy Color"),
    ("Gearboy (Game Boy Color)", "gearboy", "Nintendo Game Boy Color"),
    ("Gearsystem (Sega Master System/Gamegear)", "gearsystem", "Sega Master System/Gamegear"),
    ("Genesis Plus GX (Sega Genesis)", "genesis_plus_gx", "Sega Genesis"),
    ("Handy (Atari Lynx)", "handy", "Atari Lynx"),
    ("Hatari (Atari ST/STE/TT/Falcon)", "hatari", "Atari ST/STE/TT/Falcon"),
    ("HBMAME (Arcade)", "hbmame", "Arcade"),
    ("higan accuracy(Super Nintendo)", "higan_sfc", "Nintendo SNES"),
    ("higan balanced(Super Nintendo)", "higan_sfc_balanced", "Nintendo SNES"),
    ("Kronos (Sega Saturn)", "kronos", "Sega Saturn"),
    ("MAME (Arcade)", "mame", "Arcade"),
    ("MAME 2003-Plus (Arcade)", "mame2003_plus", "Arcade"),
    ("Mednafen GBA (Game Boy Advance)", "mednafen_gba", "Nintendo Game Boy Advance"),
    ("Mednafen NGP (SNK Neo Geo Pocket)", "mednafen_ngp", "SNK Neo Geo Pocket"),
    ("Mednafen PCE (TurboGrafx-16)", "mednafen_pce", "NEC PC Engine (TurboGrafx-16)"),
    ("Mednafen PCE FAST (TurboGrafx-16)", "mednafen_pce_fast", "NEC PC Engine (TurboGrafx-16)"),
    ("Mednafen PCFX (NEC PC-FX)", "mednafen_pcfx", "NEC PC-FX"),
    ("Mednafen Saturn (Sega Saturn)", "mednafen_saturn", "Sega Saturn"),
    ("Mednafen SGX (NEC PC Engine SuperGrafx)",
     "mednafen_supergrafx",
     "NEC PC Engine (SuperGrafx)"),
    ("Mednafen WSWAN (Bandai WonderSwan)", "mednafen_wswan", "Bandai WonderSwan"),
    ("Mednafen PSX (Sony Playstation)", "mednafen_psx", "Sony PlayStation"),
    ("Mednafen PSX OpenGL (Sony Playstation)", "mednafen_psx_hw", "Sony PlayStation"),
    ("Mesen (Nintendo Entertainment System)", "mesen", "Nintendo NES"),
    ("Mesen-S (Super Nintendo)", "mesen-s", "Nintendo SNES"),
    ("melonDS (Nintendo DS)", "melonds", "Nintendo DS"),
    ("mGBA (Game Boy Advance)", "mgba", "Nintendo Game Boy Advance"),
    ("Mupen64Plus (Nintendo 64)", "mupen64plus", "Nintendo N64"),
    ("Nestopia (Nintendo Entertainment System)", "nestopia", "Nintendo NES"),
    ("Neko Project 2 (NEC PC-98)", "nekop2", "NEC PC-98"),
    ("Neko Project II kai (NEC PC-98)", "np2kai", "NEC PC-98"),
    ("NeoCD (SNK Neo Geo CD)", "neocd", "SNK Neo Geo CD"),
    ("O2EM (Magnavox Odyssey²)", "o2em", "Magnavox Odyssey²"),
    ("Opera (3DO)", "opera", "3DO"),
    ("ParaLLEl N64 (Nintendo 64)", "parallel_n64", "Nintendo N64"),
    ("PCSX Rearmed (Sony Playstation)", "pcsx_rearmed", "Sony PlayStation"),
    ("PicoDrive (Sega Genesis)", "picodrive", "Sega Genesis"),
    ("Play! (Sony Playstation 2)", "play", "Sony PlayStation 2"),
    ("Portable SHARP X68000 Emulator (SHARP X68000)", "px68k", "Sharp X68000"),
    ("PPSSPP (PlayStation Portable)", "ppsspp", "Sony PlayStation Portable"),
    ("ProSystem (Atari 7800)", "prosystem", "Atari 7800"),
    ("QUASI88 (NEC PC-8801)", "quasi88", "NEC PC-8801"),
    ("RACE (SNK Neo Geo Pocket)", "race", "SNK Neo Geo Pocket"),
    ("RPG Maker 2000/2003 (EasyRPG)", "easyrpg", "RPG Maker 2000/2003 Game Engine"),
    ("Snes9x (Super Nintendo)", "snes9x", "Nintendo SNES"),
    ("Snes9x2010 (Super Nintendo)", "snes9x2010", "Nintendo SNES"),
    ("Stella (Atari 2600)", "stella", "Atari 2600"),
    ("Stella 2014 (Atari 2600)", "stella2014", "Atari 2600"),
    ("smsplus (Sega - MS/GG)", "smsplus", "Sega MS/GG"),
    ("Tic-80 (Tic-80)", "tic80", "TIC-80"),
    ("Uzem (Uzebox)", "uzem", "Uzebox"),
    ("VecX (Vectrex)", "vecx", "Vectrex"),
    ("Yabause (Sega Saturn)", "yabause", "Sega Saturn"),
    ("VBA Next (Game Boy Advance)", "vba_next", "Nintendo Game Boy Advance"),
    ("VBA-M (Game Boy Advance)", "vbam", "Nintendo Game Boy Advance"),
    ("Virtual Jaguar (Atari Jaguar)", "virtualjaguar", "Atari Jaguar"),
    ("VICE (Commodore 128)", "vice_x128", "Commodore 128"),
    ("VICE (Commodore CBM-II)", "vice_xcbm2", "Commodore CBM-II"),
    ("VICE (Commodore Pet)", "vice_xpet", "Commodore Pet"),
    ("VICE (Commodore 16/Plus/4)", "vice_xplus4", "Commodore 16/Plus/4"),
    ("VICE (Commodore 64)", "vice_x64", "Commodore 64"),
    ("VICE (Commodore 64)(Cycle-Exact)", "vice_x64sc", "Commodore 64"),
    ("VICE (Commodore VIC-20)", "vice_xvic", "Commodore VIC-20"),
    ("vitaQuake 2 (Quake 2)", "vitaquake2", "vitaQuake 2"),
    ("vitaQuake 3 (Quake 3)", "vitaquake3", "vitaQuake 3"),
]


def get_core_choices():
    return [(core[0], core[1]) for core in LIBRETRO_CORES]


def get_default_config_path(path=""):
    return os.path.join(settings.RUNNER_DIR, "retroarch", path)


class libretro(Runner):
    human_name = "Libretro"
    description = "Multi system emulator"
    runnable_alone = True
    runner_executable = "retroarch/retroarch"

    game_options = [
        {"option": "main_file", "type": "file", "label": "ROM file"},
        {
            "option": "core",
            "type": "choice",
            "label": "Core",
            "choices": get_core_choices(),
        },
    ]

    runner_options = [
        {
            "option": "config_file",
            "type": "file",
            "label": "Config file",
            "default": get_default_config_path("retroarch.cfg"),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": True,
        },
        {
            "option": "verbose",
            "type": "bool",
            "label": "Verbose logging",
            "default": False,
        },
    ]

    @property
    def platforms(self):
        return [core[2] for core in LIBRETRO_CORES]

    def get_platform(self):
        game_core = self.game_config.get("core")
        if game_core:
            for core in LIBRETRO_CORES:
                if core[1] == game_core:
                    return core[2]
        return ""

    def get_core_path(self, core):
        return os.path.join(
            settings.RUNNER_DIR, "retroarch", "cores", "{}_libretro.so".format(core)
        )

    def get_version(self, use_default=True):
        return self.game_config["core"]

    def is_retroarch_installed(self):
        return system.path_exists(self.get_executable())

    def is_installed(self, core=None):
        if self.game_config.get("core") and core is None:
            core = self.game_config["core"]
        if not core or self.runner_config.get("runner_executable"):
            return self.is_retroarch_installed()

        is_core_installed = system.path_exists(self.get_core_path(core))
        return self.is_retroarch_installed() and is_core_installed

    def install(self, version=None, downloader=None, callback=None):
        def install_core():
            if not version:
                if callback:
                    callback()
            else:
                super(libretro, self).install(version, downloader, callback)

        if not self.is_retroarch_installed():
            super(libretro, self).install(
                version=None, downloader=downloader, callback=install_core
            )
        else:
            super(libretro, self).install(version, downloader, callback)

    def get_run_data(self):
        return {
            "command": [self.get_executable()] + self.get_runner_parameters(),
            "env": self.get_env(),
        }

    def get_config_file(self):
        return self.runner_config.get("config_file") or get_default_config_path(
            "retroarch.cfg"
        )

    @staticmethod
    def get_system_directory(retro_config):
        """Return the system directory used for storing BIOS and firmwares."""
        system_directory = retro_config["system_directory"]
        if not system_directory or system_directory == "default":
            system_directory = get_default_config_path("system")
        return os.path.expanduser(system_directory)

    def prelaunch(self):
        config_file = self.get_config_file()

        # Create retroarch.cfg if it doesn't exist.
        if not system.path_exists(config_file):
            f = open(config_file, "w")
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
            retro_config.save()
        else:
            retro_config = RetroConfig(config_file)

        core = self.game_config.get("core")
        info_file = os.path.join(
            get_default_config_path("info"), "{}_libretro.info".format(core)
        )
        if system.path_exists(info_file):
            core_config = RetroConfig(info_file)
            try:
                firmware_count = int(core_config["firmware_count"])
            except (ValueError, TypeError):
                firmware_count = 0
            system_path = self.get_system_directory(retro_config)
            notes = core_config["notes"] or ""
            checksums = {}
            if notes.startswith("Suggested md5sums:"):
                parts = notes.split("|")
                for part in parts[1:]:
                    checksum, filename = part.split(" = ")
                    checksums[filename] = checksum
            for index in range(firmware_count):
                firmware_filename = core_config["firmware%d_path" % index]
                firmware_path = os.path.join(system_path, firmware_filename)
                if system.path_exists(firmware_path):
                    if firmware_filename in checksums:
                        checksum = system.get_md5_hash(firmware_path)
                        if checksum == checksums[firmware_filename]:
                            checksum_status = "Checksum good"
                        else:
                            checksum_status = "Checksum failed"
                    else:
                        checksum_status = "No checksum info"
                    logger.info(
                        "Firmware '%s' found (%s)", firmware_filename, checksum_status
                    )
                else:
                    logger.warning("Firmware '%s' not found!", firmware_filename)

                # Before closing issue #431
                # TODO check for firmware*_opt and display an error message if
                # firmware is missing
                # TODO Add dialog for copying the firmware in the correct
                # location

        return True

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
        command = [self.get_executable()]

        command += self.get_runner_parameters()

        # Core
        core = self.game_config.get("core")
        if not core:
            return {
                "error": "CUSTOM",
                "text": "No core has been selected for this game",
            }
        command.append("--libretro={}".format(self.get_core_path(core)))

        # Ensure the core is available
        if not self.is_installed(core):
            self.install(core)

        # Main file
        file = self.game_config.get("main_file")
        if not file:
            return {"error": "CUSTOM", "text": "No game file specified"}
        if not system.path_exists(file):
            return {"error": "FILE_NOT_FOUND", "file": file}
        command.append(file)
        return {"command": command}

    # Checks whether the retroarch or libretro directories can be uninstalled.
    def can_uninstall(self):
        retroarch_path = os.path.join(settings.RUNNER_DIR, 'retroarch')
        return os.path.isdir(retroarch_path) or super(libretro, self).can_uninstall()

    # Remove the `retroarch` directory.
    def uninstall(self):
        retroarch_path = os.path.join(settings.RUNNER_DIR, 'retroarch')
        if os.path.isdir(retroarch_path):
            system.remove_folder(retroarch_path)
        super(libretro, self).uninstall()
