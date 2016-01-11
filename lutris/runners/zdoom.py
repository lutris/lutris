import os
from lutris import settings
from lutris.runners.runner import Runner

class zdoom(Runner):
    description = "ZDoom DOOM Game Engine"
    human_name = "ZDoom"
    platform = "PC"
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'WAD file',
            'help': ("The game data, commonly called a WAD file.")
        }
    ]
    runner_options = [
        {
            "option": "2",
            "label": "Pixel Doubling",
            "type": "bool",
            'default': False
        },
        {
            "option": "4",
            "label": "Pixel Quadrupling",
            "type": "bool",
            'default': False
        },
        {
            "option": "nostartup",
            "label": "Disable Startup Screens",
            "type": "bool",
            'default': False
        },
        {
            "option": "nosound",
            "label": "Disable Both Music and Sound Effects",
            "type": "bool",
            'default': False,
        },
        {
            "option": "nosfx",
            "label": "Disable Sound Effects",
            "type": "bool",
            'default': False
        },
        {
            "option": "nomusic",
            "label": "Disable Music",
            "type": "bool",
            'default': False
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'zdoom/zdoom')

    @property
    def working_dir(self):
        return os.path.dirname(self.main_file) \
            or super(zdoom, self).working_dir

    def play(self):
        command = [
            self.get_executable()
        ]

        resolution = self.runner_config.get("resolution")
        if resolution:
            if resolution == 'desktop':
                resolution = display.get_current_resolution()
            width, height = resolution.split('x')
            command.append("-width %s" % width)
            command.append("-height %s" % height)

        # Append any boolean options.
        boolOptions = ['nomusic', 'nosfx', 'nosound', '2', '4', 'nostartup']
        for option in boolOptions:
            if self.runner_config.get(option):
                command.append('-%s' % option)

        # Append the wad file to load, if provided.
        wad = self.game_config.get('main_file')
        if wad:
            command.append('-iwad %s' % wad)

        return {'command': command}
