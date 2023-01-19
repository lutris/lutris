
DEFAULT_INSTALLERS = {
    "3do": {
        "runner": "libretro",
        "game": { "core": "opera", "main_file": "rom" },
    },
    "sms": {
        "runner": "libretro",
        "game": { "core": "genesis_plus_gx", "main_file": "rom" },
    },
    "md": {
        "runner": "libretro",
        "game": { "core": "genesis_plus_gx", "main_file": "rom" },
    },
    "colecovision": {
        "runner": "mame",
        "game": { "main_file": "rom", "machine": "coleco", "device": "cart" }
    },
    "atari-st": {
        "runner": "hatari",
        "game": { "disk-a": "rom" }
    },
    "amiga": {
        "runner": "fsuae",
        "game": { "main_file": "rom" }
    },
    "amiga-1200": {
        "runner": "fsuae",
        "game": { "main_file": "rom" },
        "fsuae": { "model": "A1200" }
    }
}
