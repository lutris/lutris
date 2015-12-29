import os
import shutil
from lutris.settings import RUNNER_DIR


def migrate():
    for dirname in os.listdir(RUNNER_DIR):
        path = os.path.join(RUNNER_DIR, dirname)
        if not os.path.isdir(path):
            return
        if dirname in ['atari800', 'dgen', 'dolphin', 'dosbox', 'frotz', 'fs-uae',
                       'gens', 'hatari', 'jzintv', 'mame', 'mednafen', 'mess',
                       'mupen64plus', 'nulldc', 'o2em', 'osmose', 'pcsxr',
                       'reicast', 'ResidualVM', 'residualvm', 'scummvm',
                       'snes9x', 'stella', 'vice', 'virtualjaguar', 'zdoom']:
            shutil.rmtree(path)
