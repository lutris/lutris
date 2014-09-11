# -*- coding: utf-8 -*-
import os
import subprocess
from lutris import settings
from lutris.util.log import logger
from lutris.runners.runner import Runner


def dosexec(config_file):
    """Execute Dosbox with given config_file"""
    logger.debug("Running dosbox with config %s" % config_file)
    dbx = dosbox()
    command = '"%s" -conf "%s"' % (dbx.get_executable(), config_file)
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).communicate()


class dosbox(Runner):
    """Runner for MS Dos games"""
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

    tarballs = {
        "x64": "dosbox-0.74-x86_64.tar.gz",
    }

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, "dosbox/bin/dosbox")

    def play(self):
        self.exe = self.settings["game"]["main_file"]
        if not os.path.exists(self.exe):
            return {'error': "FILE_NOT_FOUND", 'file': self.exe}
        if self.exe.endswith(".conf"):
            exe = ["-conf", '"%s"' % self.exe]
        else:
            exe = ['"%s"' % self.exe]
        if "config_file" in self.settings["game"]:
            params = ["-conf", '"%s"' % self.settings["game"]["config_file"]]
        else:
            params = []
        return {'command': [self.get_executable()] + params + exe}
