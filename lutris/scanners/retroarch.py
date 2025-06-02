import os

from lutris.config import write_game_config
from lutris.database.games import add_game, get_games
from lutris.util.log import logger
from lutris.util.retroarch.core_config import RECOMMENDED_CORES
from lutris.util.strings import slugify

SCANNERS = {
    "mesen": "NES",
    "gambatte": "Gameboy / Gameboy Color",
    "snes": "Super Nintendo",
    "mupen64plus_next": "Nintendo 64",
    "picodrive": "Master System / Game Gear / Genesis / MegaCD / 32x",
    "opera": "3DO",
}


ROM_FLAGS = [
    "USA",
    "Europe",
    "World",
    "Japan",
    "Japan, USA",
    "USA, Europe",
    "Proto",
    "SGB Enhanced",
    "Rev A",
    "V1.1",
    "F",
    "U",
    "E",
    "UE",
    "W",
    "M3",
]

EXTRA_FLAGS = ["!", "S"]


def clean_rom_name(name):
    """Remove known flags from ROM filename and apply formatting"""
    for flag in ROM_FLAGS:
        name = name.replace(" (%s)" % flag, "")
    for flag in EXTRA_FLAGS:
        name = name.replace("[%s]" % flag, "")
    if ", The" in name:
        name = "The %s" % name.replace(", The", "")
    name = name.strip()
    return name


def scan_directory(dirname):
    """Add a directory of ROMs as Lutris games"""
    files = os.listdir(dirname)
    folder_extensions = {os.path.splitext(filename)[1] for filename in files}
    core_matches = {}
    for core, core_data in RECOMMENDED_CORES.items():
        for ext in core_data.get("extensions", []):
            if ext in folder_extensions:
                core_matches[ext] = core
    added_games = []
    for filename in files:
        name, ext = os.path.splitext(filename)
        if ext not in core_matches:
            continue
        logger.info("Importing '%s'", name)
        slug = slugify(name)
        core = core_matches[ext]
        config = {"game": {"core": core_matches[ext], "main_file": os.path.join(dirname, filename)}}
        installer_slug = "%s-libretro-%s" % (slug, core)
        existing_game = get_games(filters={"installer_slug": installer_slug})
        if existing_game:
            continue
        configpath = write_game_config(slug, config)
        game_id = add_game(
            name=name,
            runner="libretro",
            slug=slug,
            directory=dirname,
            installed=1,
            installer_slug=installer_slug,
            configpath=configpath,
        )
        added_games.append(game_id)
    return added_games
