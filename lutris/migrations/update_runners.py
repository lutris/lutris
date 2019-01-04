import os
import shutil
from lutris.settings import RUNNER_DIR
from lutris.util import system


def migrate():
    for dirname in os.listdir(RUNNER_DIR):
        path = os.path.join(RUNNER_DIR, dirname)
        if not os.path.isdir(path):
            return
        if dirname in [
            "atari800",
            "dgen",
            "dolphin",
            "dosbox",
            "frotz",
            "fs-uae",
            "gens",
            "hatari",
            "jzintv",
            "mame",
            "mednafen",
            "mess",
            "mupen64plus",
            "nulldc",
            "o2em",
            "osmose",
            "reicast",
            "ResidualVM",
            "residualvm",
            "scummvm",
            "snes9x",
            "stella",
            "vice",
            "virtualjaguar",
            "zdoom",
        ]:
            system.remove_folder(path)
