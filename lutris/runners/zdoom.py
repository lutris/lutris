import os
from lutris.util import display
from lutris.runners.runner import Runner


class zdoom(Runner):
    # http://zdoom.org/wiki/Command_line_parameters
    description = "ZDoom DOOM Game Engine"
    human_name = "ZDoom"
    platforms = ["Linux"]
    runner_executable = 'zdoom/zdoom'
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'WAD file',
            'help': ("The game data, commonly called a WAD file.")
        },
        {
            'option': 'files',
            'type': 'multiple',
            'label': 'PWAD files',
            'help': ("Used to load one or more PWAD files which generally contain "
                     "user-created levels.")
        },
        {
            'option': 'warp',
            'type': 'string',
            'label': 'Warp to map',
            'help': ("Starts the game on the given map.")
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
            "option": "skill",
            "label": "Skill",
            "type": "choice",
            "default": '',
            "choices": {
                ("None", ''),
                ("I'm Too Young To Die (0)", '0'),
                ("Hey, Not Too Rough (1)", '1'),
                ("Hurt Me Plenty (2)", '2'),
                ("Ultra-Violence (3)", '3'),
                ("Nightmare! (4)", '4'),
            }
        }
    ]

    @property
    def working_dir(self):
        # Run in the installed game's directory.
        return self.game_path

    def get_executable(self):
        executable = super(zdoom, self).get_executable()
        executable_dir = os.path.dirname(executable)
        if not os.path.exists(executable_dir):
            return executable
        if not os.path.exists(executable):
            gzdoom_executable = os.path.join(executable_dir, 'gzdoom')
            if os.path.exists(gzdoom_executable):
                return gzdoom_executable
        return executable

    def play(self):
        command = [self.get_executable()]

        resolution = self.runner_config.get("resolution")
        if resolution:
            if resolution == 'desktop':
                resolution = display.get_current_resolution()
            width, height = resolution.split('x')
            command.append("-width")
            command.append(width)
            command.append("-height")
            command.append(height)

        # Append any boolean options.
        bool_options = ['2', '4', 'nostartup']
        for option in bool_options:
            if self.runner_config.get(option):
                command.append("-%s" % option)

        # Append the skill level.
        skill = self.runner_config.get('skill')
        if skill:
            command.append("-skill")
            command.append(skill)

        # Append the warp arguments.
        warp = self.game_config.get('warp')
        if warp:
            command.append("-warp")
            for warparg in warp.split(' '):
                command.append(warparg)

        # Append the wad file to load, if provided.
        wad = self.game_config.get('main_file')
        if wad:
            command.append("-iwad")
            command.append(wad)

        # Append the pwad files to load, if provided.
        files = self.game_config.get('files') or []
        pwads = [f for f in files if f.lower().endswith('.wad') or f.lower().endswith('.pk3')]
        deh = [f for f in files if f.lower().endswith('.deh')]
        bex = [f for f in files if f.lower().endswith('.bex')]
        if deh:
            command.append('-deh')
            command.append(deh[0])
        if bex:
            command.append('-bex')
            command.append(bex[0])
        if pwads:
            command.append("-file")
            for pwad in pwads:
                command.append(pwad)

        return {'command': command}
