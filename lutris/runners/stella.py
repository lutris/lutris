import os
from lutris.runners.runner import Runner


class stella(Runner):
    description = _("Atari 2600 emulator")
    human_name = "Stella"
    platforms = ['Atari 2600']
    runnable_alone = True
    runner_executable = "stella/bin/stella"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            'help': _(
                "The game data, commonly called a ROM image."
                "Supported formats: A26/BIN/ROM. GZIP and ZIP compressed "
                "ROMs are supported."
            )
        }
    ]
    runner_options = []

    def play(self):
        cart = self.game_config.get('main_file') or ''
        if not os.path.exists(cart):
            return {'error': 'FILE_NOT_FOUND', 'file': cart}
        return {'command': [self.get_executable(), cart]}
