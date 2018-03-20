import os
from lutris.runners.runner import Runner


class osmose(Runner):
    human_name = "Osmose"
    description = _("Sega Master System Emulator")
    platforms = ['Sega Master System']
    runner_executable = 'osmose/osmose'
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': _('ROM file'),
            'default_path': 'game_path',
            'help': _(
                "The game data, commonly called a ROM image."
                "Supported formats: SMS and GG files. ZIP compressed "
                "ROMs are supported."
            )
        }
    ]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': _('Fullscreen'),
            'default': False,
        }
    ]

    def play(self):
        """Run Sega Master System game"""
        arguments = [self.get_executable()]
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        if self.runner_config.get('fullscreen'):
            arguments.append('-fs')
            arguments.append('-bilinear')
        return {'command': arguments}
