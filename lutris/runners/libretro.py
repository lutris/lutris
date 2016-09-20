import os
from lutris.runners.runner import Runner
from lutris import settings


def get_cores():
    return [
        ('libretro-snes.so', 'SNES'),
    ]


class libretro(Runner):
    human_name = "libretro"
    description = "Multi system emulator"
    platform = "libretro"
    runnable_alone = True
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
        },
        {
            'option': 'core',
            'type': 'choice',
            'label': 'Core',
            'choices': get_cores(),
        }
    ]

    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': True
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'retroarch/retroarch')

    def play(self):
        command = [self.get_executable()]

        # Fullscreen
        fullscreen = self.runner_config.get('fullscreen')
        if fullscreen:
            command.append('--fullscreen')

        # Core
        core = self.game_config.get('core')
        if core:
            command.append('-L')
            command.append(core)

        # Main file
        file = self.game_config.get('main_file')
        if file:
            command.append(file)

        return {'command': command}
