# -*- coding:Utf-8 -*-
""" Runner for MS Dos games """
import os
import subprocess
from lutris.util.log import logger
from lutris.runners.runner import Runner


def dosexec(config_file):
    logger.debug("Running dosbox with config %s" % config_file)
    subprocess.Popen("dosbox -conf %s" % config_file, shell=True,
                     stdout=subprocess.PIPE).communicate()


# pylint: disable=C0103
class dosbox(Runner):
    """Runner for MS Dos games"""
    def __init__(self, settings=None):
        """Constructor"""
        super(dosbox, self).__init__()
        self.package = "dosbox"
        self.executable = "dosbox"
        self.platform = "MS DOS"
        self.description = "DOS Emulator"
        self.game_options = [
            {
                "option": "main_file",
                "type": "file_chooser",
                "label": "EXE File"
            },
            {
                "option": "config_file",
                "type": "file_chooser",
                "label": "Configuration file"
            }
        ]
        self.runner_options = []
        self.settings = settings

    def play(self):
        """ Run the game """
        logger.debug(self.settings)
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
