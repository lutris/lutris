# -*- coding: utf-8 -*-
import os
from lutris.util.log import logger
from lutris.util import system
from lutris.runners.runner import Runner


def dosexec(config_file=None, executable=None, args=None, exit=True,
            working_dir=None):
    """Execute Dosbox with given config_file."""
    if config_file:
        run_with = "config {}".format(config_file)
        if not working_dir:
            working_dir = os.path.dirname(config_file)
    elif executable:
        run_with = "executable {}".format(executable)
        if not working_dir:
            working_dir = os.path.dirname(executable)
    else:
        raise ValueError("Neither a config file or an executable were provided")
    logger.debug("Running dosbox with {}".format(run_with))
    working_dir = system.create_folder(working_dir)
    dosbox_runner = dosbox()
    command = [dosbox_runner.get_executable()]
    if config_file:
        command += ['-conf', config_file]
    if executable:
        if not os.path.exists(executable):
            raise OSError("Can't find file {}".format(executable))
        command += [executable]
    if args:
        command += args.split()
    if exit:
        command.append('-exit')
    system.execute(command, cwd=working_dir)


def makeconfig(path, drives, commands):
    system.create_folder(os.path.dirname(path))
    with open(path, 'w') as config_file:
        config_file.write('[autoexec]\n')
        for drive in drives:
            config_file.write("mount {} \"{}\"\n".format(drive, drives[drive]))
        for command in commands:
            config_file.write("{}\n".format(command))


class dosbox(Runner):
    human_name = "DOSBox"
    description = _("MS-Dos emulator")
    platforms = ["MS-DOS"]
    description = _("DOS Emulator")
    runnable_alone = True
    runner_executable = "dosbox/bin/dosbox"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Main file"),
            'help': _(
                "The CONF, EXE, COM or BAT file to launch."
                 "It can be left blank if the launch of the executable is"
                 "managed in the config file."
            )
        },
        {
            "option": "config_file",
            "type": "file",
            "label": _("Configuration file"),
            'help': _(
                "Start Dosbox with the options specified in this file."
                 "It can have a section in which you can put commands "
                 "to execute on startup. Read Dosbox's documentation "
                 "for more information."
            )
        },
        {
            'option': 'args',
            'type': 'string',
            'label': _('Command arguments'),
            'help': _(
                "Command line arguments used when launching "
                 "DOSBox"
            )
        },
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
            "label": _("Graphic scaler"),
            "type": "choice",
            "choices": scaler_modes,
            "default": "normal3x",
            'help': _(
                "The algorithm used to scale up the game's base "
                 "resolution, resulting in different visual styles. "
            )
        },
        {
            "option": "exit",
            "label": _("Exit Dosbox with the game"),
            "type": "bool",
            "default": True,
            'help': _(
                "Shut down Dosbox when the game is quit."
            )
        },
        {
            "option": "fullscreen",
            "label": _("Open game in fullscreen"),
            "type": "bool",
            "default": False,
            'help': _("Tells Dosbox to launch the game in fullscreen.")
        }
    ]

    @property
    def main_file(self):
        main_file = self.game_config.get('main_file')
        if not main_file:
            return ''
        if os.path.isabs(main_file):
            return main_file
        game_directory = self.game_data.get('directory')
        if game_directory:
            return os.path.join(game_directory, main_file)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return os.path.dirname(self.main_file) \
            or super(dosbox, self).working_dir

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

        scaler = self.runner_config.get('scaler')
        if scaler and scaler != 'none':
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
