from lutris.runners.runner import Runner


class vice(Runner):
    """ Commodore Emulator """
    package = "vice"
    executable = "x64"
    platform = "Commodore 64"

    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": "Disk File"
    }]

    runner_options = [
        {
            "option": "joy",
            "type": "bool",
            "label": "Use joysticks"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        {
            "option": "double",
            "type": "bool",
            "label": "Double Size"
        }
    ]

    def play(self):
        params = [self.executable]
        if self.runner_config.get("fullscreen"):
            params.append("-fullscreen")
        if self.runner_config.get("double"):
            params.append("-VICIIdsize")
        if self.runner_config.get("joy"):
            params += ["-joydev2", "4", "-joydev1", "5"]
        params.append("\"%s\"" % self.settings['game']['main_file'])
        return {'command': [self.executable] + params}
