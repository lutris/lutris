"""Runner for stella Atari 2600 emulator"""
import os
from lutris import settings
from lutris.runners.runner import Runner


class stella(Runner):
    """Atari 2600 games emulator"""
    platform = "Atari 2600"
    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": "Cartridge"
    }]
    runner_options = []

    tarballs = {
        "x64": "stella-4.0-x86_64.tar.gz",
    }

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, "stella/bin/stella")

    def play(self):
        cart = self.settings["game"].get("main_file")
        return {'command': [self.get_executable(), "\"%s\"" % cart]}
