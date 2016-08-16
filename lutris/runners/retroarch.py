from lutris.runners.runner import Runner


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
            'choices': (),
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
