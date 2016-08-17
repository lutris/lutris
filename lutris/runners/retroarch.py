import os
from lutris.runners.runner import Runner
from lutris import settings


def get_cores():
    return [
        ('libretro-snes.so', 'SNES'),
    ]


class retroarch(Runner):
    human_name = "RetroArch"
    description = "Frontend for libretro cores"
    platform = "RetroArch"
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
