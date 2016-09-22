import os

from lutris.runners.runner import Runner


class ags(Runner):
    human_name = "Adventure Game Studio"
    description = "Graphics adventure engine"
    platform = 'Linux'
    runner_executable = 'ags/ags.sh'
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label':  'blopblup '
    }]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': True
        }
    ]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        if self.runner_config.get('fullscreen', True):
            arguments.append('-f')
        main_file = self.game_config.get('main_file') or ''
        if not os.path.exists(main_file):
            return {'error': 'FILE_NOT_FOUND', 'file': main_file}
        arguments.append(main_file)
        return {"command": arguments}
