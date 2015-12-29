import os
from lutris import settings
from lutris.runners.runner import Runner

class zdoom(Runner):
    description = "ZDoom DOOM Game Engine"
    human_name = "ZDoom"
    platform = "PC"
    game_options = [
        # TODO: Add options from http://zdoom.org/wiki/Command_line_parameters .
    ]
    runner_options = [
        # TODO: Add options from http://zdoom.org/wiki/Command_line_parameters .
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'zdoom/zdoom')

    @property
    def working_dir(self):
        option = self.game_config.get('working_dir')
        if option:
            return option
        if self.game_path:
            return self.game_path
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        else:
            return super(wine, self).working_dir

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

        return {'command': command}
