import os

from lutris.config import write_game_config
from lutris.database.games import add_game, get_games
from lutris.game import Game
from lutris.util.retroarch.core_config import RECOMMENDED_CORES
from lutris.util.strings import slugify

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
    "W",
    "M3"
]

EXTRA_FLAGS = [
    "!",
    "S"
]


def scan_directory(dirname):
    files = os.listdir(dirname)
    folder_extentions = {os.path.splitext(filename)[1] for filename in files}
    core_matches = {}
    for core in RECOMMENDED_CORES:
        for ext in RECOMMENDED_CORES[core].get("extensions", []):
            if ext in folder_extentions:
                core_matches[ext] = core
    added_games = []
    for filename in files:
        name, ext = os.path.splitext(filename)
        if ext not in core_matches:
            continue
        for flag in ROM_FLAGS:
            name = name.replace(" (%s)" % flag, "")
        for flag in EXTRA_FLAGS:
            name = name.replace("[%s]" % flag, "")
        if ", The" in name:
            name = "The %s" % name.replace(", The", "")
        name = name.strip()
        print("Importing '%s'" % name)
        slug = slugify(name)
        core = core_matches[ext]
        config = {
            "game": {
                "core": core_matches[ext],
                "main_file": os.path.join(dirname, filename)
            }
        }
        installer_slug = "%s-libretro-%s" % (slug, core)
        existing_game = get_games(filters={"installer_slug": installer_slug, "installed": "1"})
        if existing_game:
            game = Game(existing_game[0]["id"])
            game.remove()
        configpath = write_game_config(slug, config)
        game_id = add_game(
            name=name,
            runner="libretro",
            slug=slug,
            directory=dirname,
            installed=1,
            installer_slug=installer_slug,
            configpath=configpath
        )
        print("Imported %s" % name)
        added_games.append(game_id)
    return added_games
