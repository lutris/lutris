import os
from lutris.runners.runner import Runner
from lutris.runners.commands.dosbox import (
    dosexec,
    makeconfig
)


class dosbox(Runner):
    human_name = "DOSBox"
    description = "MS-Dos emulator"
    platforms = ["MS-DOS"]
    runnable_alone = True
    runner_executable = "dosbox/bin/dosbox"
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
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": "Working directory",
            'help': ("The location where the game is run from.\n"
                     "By default, Lutris uses the directory of the "
                     "executable.")
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
            "label": "Graphic scaler",
            "type": "choice",
            "choices": scaler_modes,
            "default": "normal3x",
            'help': ("The algorithm used to scale up the game's base "
                     "resolution, resulting in different visual styles. ")
        },
        {
            "option": "exit",
            "label": "Exit Dosbox with the game",
            "type": "bool",
            "default": True,
            'help': "Shut down Dosbox when the game is quit."
        },
        {
            "option": "fullscreen",
            "label": "Open game in fullscreen",
            "type": "bool",
            "default": False,
            'help': "Tells Dosbox to launch the game in fullscreen."
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
        option = self.game_config.get('working_dir')
        if option:
            return os.path.expanduser(option)
        if self.main_file:
            return os.path.dirname(self.main_file)
        return super(dosbox, self).working_dir

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

        return {'command': command}
