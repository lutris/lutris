from lutris.runners.runner import Runner


class virtualjaguar(Runner):
    """ Run Atari Jaguar games """
    executable = "virtualjaguar"
    platform = "Atari Jaguar"
    is_installable = True

    game_options = [
        {
            "option": "main_file",
            "type": "file_chooser",
            "default_path": "game_path",
            "label": "ROM"
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

    def __init__(self, settings=None):
        super(virtualjaguar, self).__init__()


    def play(self):
        pass

