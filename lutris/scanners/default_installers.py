
DEFAULT_INSTALLERS = {
    "3do": {
        "runner": "libretro",
        "game": {"core": "opera", "main_file": "rom"},
    },
    "sms": {
        "runner": "libretro",
        "game": {"core": "genesis_plus_gx", "main_file": "rom"},
    },
    "gg": {
        "runner": "libretro",
        "game": {"core": "genesis_plus_gx", "main_file": "rom"},
    },
    "md": {
        "runner": "libretro",
        "game": {"core": "genesis_plus_gx", "main_file": "rom"},
    },
    "pico": {
        "runner": "libretro",
        "game": {"core": "picodrive", "main_file": "rom"},
    },
    "segacd": {
        "runner": "libretro",
        "game": {"core": "picodrive", "main_file": "rom"},
    },
    "saturn": {
        "runner": "libretro",
        "game": {"core": "yabause", "main_file": "rom"},
    },
    "dc": {
        "runner": "libretro",
        "game": {"core": "flycast", "main_file": "rom"},
    },
    "colecovision": {
        "runner": "mame",
        "game": {"main_file": "rom", "machine": "coleco", "device": "cart"}
    },
    "atari800": {
        "runner": "atari800",
        "game": {"main_file": "rom", "machine": "xl"}
    },
    "atari2600": {
        "runner": "stella",
        "game": {"main_file": "rom" }
    },
    "lynx": {
        "runner": "libretro",
        "game": {"core": "handy", "main_file": "rom"},
    },
    "atari-st": {
        "runner": "hatari",
        "game": {"disk-a": "rom", }
    },
    "amiga": {
        "runner": "fsuae",
        "game": {"main_file": "rom"}
    },
    "amiga-1200": {
        "runner": "fsuae",
        "game": {"main_file": "rom"},
        "fsuae": {"model": "A1200"}
    },
    "ds": {
        "runner": "libretro",
        "game": {"core": "desmume", "main_file": "rom"},
    },
    "gb": {
        "runner": "libretro",
        "game": {"core": "gambatte", "main_file": "rom"},
    },
    "gba": {
        "runner": "libretro",
        "game": {"core": "vba_next", "main_file": "rom"},
    },
    "nes": {
        "runner": "libretro",
        "game": {"core": "mesen", "main_file": "rom"},
    },
    "snes": {
        "runner": "libretro",
        "game": {"core": "snes9x", "main_file": "rom"},
    },
    "n64": {
        "runner": "libretro",
        "game": {"core": "mupen64plus_next", "main_file": "rom"},
    },
    "gamecube": {
        "runner": "dolphin",
        "game": {"main_file": "rom", "platform": "0"}
    },
    "wii": {
        "runner": "dolphin",
        "game": {"main_file": "rom", "platform": "1"}
    },
    "switch": {
        "runner": "yuzu",
        "game": {"main_file": "rom"}
    },
    "ps1": {
        "runner": "libretro",
        "game": {"core": "mednafen_psx_hw", "main_file": "rom"},
    },
    "ps2": {
        "runner": "pcsx2",
        "game": {"main_file": "rom"}
    },
    "ps3": {
        "runner": "rpcs3",
        "game": {"main_file": "rom"}
    },
    "psp": {
        "runner": "libretro",
        "game": {"core": "ppsspp", "main_file": "rom"},
    },
    "cdi": {
        "runner": "mame",
        "game": {"main_file": "rom", "device": "cdrm", "machine": "cdimono1"}
    }
}
