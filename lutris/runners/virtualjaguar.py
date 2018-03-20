import os
from lutris.runners.runner import Runner


class virtualjaguar(Runner):
    description = _("Atari Jaguar emulator")
    human_name = "Virtual Jaguar"
    platforms = ['Atari Jaguar']
    runnable_alone = True
    runner_executable = 'virtualjaguar/virtualjaguar'
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": _("ROM file"),
            'help': _(
                "The game data, commonly called a ROM image."
                "Supported formats: J64 and JAG."
            )
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": "1"
        }
    ]

    def play(self):
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.get_executable(), rom]}
