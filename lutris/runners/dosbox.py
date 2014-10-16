# -*- coding: utf-8 -*-
import os
import subprocess
from lutris import settings
from lutris.util.log import logger
from lutris.runners.runner import Runner


def dosexec(config_file=None, executable=None):
    """Execute Dosbox with given config_file"""
    logger.debug("Running dosbox with config %s" % config_file)
    dbx = dosbox()
    command = '"{}"'.format(dbx.get_executable())
    if config_file:
        command += ' -conf "{}"'.format(config_file)
    if executable:
        command += ' "{}"'.format(executable)
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).communicate()


class dosbox(Runner):
    """Runner for MS Dos games"""
    platform = "MS DOS"
    description = "DOS Emulator"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "Executable",
            'help': ("The EXE, COM or BAT file to launch.\n"
                     "It can be left blank if the launch of the executable is"
                     "managed in the config file.")
        },
        {
            "option": "config_file",
            "type": "file",
            "label": "Configuration file",
            'help': ("Start Dosbox with the options specified in this file. \n"
                     "It can have a section in which you can put commands "
                     "to execute on startup. Read Dosbox's documentation "
                     "for more information.")
        }
    ]

    scaler_modes = [
        ("none", "none"),
        ("normal2x", "normal2x"),
        ("normal3x", "normal3x"),
        ("hq2x", "hq2x"),
        ("hq3x", "hq3x"),
        ("advmame2x", "advmame2x"),
        ("advmame3x", "advmame3x"),
        ("2xsai", "2xsai"),
        ("super2xsai", "super2xsai"),
        ("supereagle", "supereagle"),
        ("advinterp2x", "advinterp2x"),
        ("advinterp3x", "advinterp3x"),
        ("tv2x", "tv2x"),
        ("tv3x", "tv3x"),
        ("rgb2x", "rgb2x"),
        ("rgb3x", "rgb3x"),
        ("scan2x", "scan2x"),
        ("scan3x", "scan3x")
    ]
    runner_options = [
        {
            "option": "scaler",
            "label": "Graphic scaler",
            "type": "choice",
            "choices": scaler_modes,
            'help': ("The algorithm used to scale up the game's base "
                     "resolution, resulting in different visual styles. ")
        },
        {
            "option": "exit",
            "label": "Exit Dosbox with the game",
            "type": "bool",
            "default": True,
            'help': ("Shut down Dosbox when the game is quit.")
        }
    ]

    tarballs = {
        "x64": "dosbox-0.74-x86_64.tar.gz",
    }

    @property
    def main_file(self):
        return self.game_config.get('main_file') or ''

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        return os.path.dirname(self.main_file) \
            or super(dosbox, self).browse_dir

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return os.path.dirname(self.main_file) \
            or super(dosbox, self).working_dir

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, "dosbox/bin/dosbox")

    def play(self):
        main_file = self.main_file
        if not os.path.exists(main_file):
            return {'error': "FILE_NOT_FOUND", 'file': main_file}

        command = [self.get_executable()]

        if main_file.endswith(".conf"):
            command.append('-conf "%s"' % main_file)
        else:
            command.append('"%s"' % main_file)
        # Options
        if game_config.get('config_file'):
            command.append('-conf "%s"' % self.game_config['config_file'])

        if "scaler" in self.runner_config:
            command.append("-scaler %s" % self.runner_config['scaler'])

        if self.runner_config.get("exit"):
            command.append("-exit")
        # /Options

        return {'command': command}
