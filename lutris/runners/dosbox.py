# -*- coding: utf-8 -*-
import os
import subprocess
from lutris import settings
from lutris.util.log import logger
from lutris.runners.runner import Runner


def dosexec(config_file=None, executable=None, args=None, exit=True,
            working_dir=None):
    """Execute Dosbox with given config_file"""
    logger.debug("Running dosbox with config %s" % config_file)
    dbx = dosbox()
    command = '"{}"'.format(dbx.get_executable())
    if config_file:
        command += ' -conf "{}"'.format(config_file)
        if not working_dir:
            working_dir = os.path.dirname(config_file)
    if executable:
        command += ' "{}"'.format(executable)
        if not working_dir:
            working_dir = os.path.dirname(executable)
    if args:
        command += ' ' + args
    if exit:
        command += " -exit"
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                     cwd=working_dir).communicate()


class dosbox(Runner):
    """Runner for MS Dos games"""
    human_name = "DOSBox"
    platform = "MS DOS"
    description = "DOS Emulator"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "Main file",
            'help': ("The CONF, EXE, COM or BAT file to launch.\n"
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
        },
        {
            'option': 'args',
            'type': 'string',
            'label': 'Command arguments',
            'help': ("Command line arguments used when launching "
                     "DOSBox")
        },
    ]

    scaler_modes = [
        ("none", None),
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
            "default": None,
            'help': ("The algorithm used to scale up the game's base "
                     "resolution, resulting in different visual styles. ")
        },
        {
            "option": "exit",
            "label": "Exit Dosbox with the game",
            "type": "bool",
            "default": True,
            'help': ("Shut down Dosbox when the game is quit.")
        },
        {
            "option": "fullscreen",
            "label": "Open game in fullscreen",
            "type": "bool",
            "default": False,
            'help': ("Tells Dosbox to launch the game in fullscreen.")
        }
    ]

    tarballs = {
        "x64": "dosbox-0.74-x86_64.tar.gz",
    }

    @property
    def main_file(self):
        return self.game_config.get('main_file') or ''

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
        args = self.game_config.get('args') or ''

        command = [self.get_executable()]

        if main_file.endswith(".conf"):
            command.append('-conf')
            command.append(main_file)
        else:
            command.append(main_file)
        # Options
        if self.game_config.get('config_file'):
            command.append('-conf')
            command.append(self.game_config['config_file'])

        if self.runner_config.get('scaler'):
            command.append("-scaler")
            command.append(self.runner_config['scaler'])

        if self.runner_config.get("fullscreen"):
            command.append("-fullscreen")

        if self.runner_config.get("exit"):
            command.append("-exit")

        if args:
            command.append(args)
        # /Options

        return {'command': command}
