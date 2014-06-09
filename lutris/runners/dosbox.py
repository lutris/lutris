# -*- coding: utf-8 -*-
import os
import subprocess
from lutris.util.log import logger
from lutris.runners.runner import Runner


def dosexec(config_file):
    logger.debug("Running dosbox with config %s" % config_file)
    subprocess.Popen("dosbox -conf %s" % config_file, shell=True,
                     stdout=subprocess.PIPE).communicate()


class dosbox(Runner):
    """Runner for MS Dos games"""
    package = "dosbox"
    executable = "dosbox"
    platform = "MS DOS"
    description = "DOS Emulator"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "EXE File"
        },
        {
            "option": "config_file",
            "type": "file",
            "label": "Configuration file"
        }
    ]

    def get_game_path(self):
        main_file = self.settings['game'].get('main_file') or ''
        if os.path.exists(main_file):
            return os.path.dirname(main_file)

    def play(self):
        self.exe = self.settings["game"]["main_file"]
        self.game_path = os.path.dirname(self.exe)
        if not os.path.exists(self.exe):
            return {'error': "FILE_NOT_FOUND", 'file': self.exe}
        if self.exe.endswith(".conf"):
            exe = ["-conf", self.exe]
        else:
            exe = [self.exe]
        if "config_file" in self.settings["game"]:
            params = ["-conf", self.settings["game"]["config_file"]]
        else:
            params = []
        return {'command': [self.executable] + params + exe}
