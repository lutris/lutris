import os
from lutris import settings
from lutris.runners.runner import Runner

# ZDoom Runner
# http://zdoom.org/wiki/Command_line_parameters
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
        },
        {
            'option': 'file',
            'type': 'file',
            'label': 'PWAD file',
            'help': ("Used to load one or more PWAD files which generally contain user-created levels.")
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
        },
        {
            "option": "skill",
            "label": "Skill",
            "type": "choice",
            "default": '',
            "choices": {
                ("None", ''),
                ("Please Don't Kill Me (0)", '0'),
                ("Will This Hurt? (1)", '1'),
                ("Bring On The Pain (2)", '2'),
                ("Extreme Carnage (3)", '3'),
                ("Insanity! (4)", '4'),
            }
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'zdoom')

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

        # Append the skill level.
        skill = self.game_config.get('skill')
        if skill:
            command.append('-skill %s' % skill)

        # Append the wad file to load, if provided.
        wad = self.game_config.get('main_file')
        if wad:
            command.append('-iwad %s' % wad)

        # Append the pwad files to load, if provided.
        pwad = self.game_config.get('file')
        if pwad:
            command.append('-file %s' % pwad)

        return {'command': command}
