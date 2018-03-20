import os

from lutris.runners.runner import Runner


class citra(Runner):
    human_name = "Citra"
    platforms = ['Nintendo 3DS']
    description = 'Nintendo 3DS emulator'
    runner_executable = 'citra/citra-qt'
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label': _('ROM file'),
        'help': _("The game data, commonly called a ROM image.")
    }]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        return {"command": arguments}
