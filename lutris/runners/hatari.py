import os
from lutris.runners.runner import Runner


class hatari(Runner):
    """Atari ST computers"""
    package = "hatari"
    executable = "hatari"
    platform = "Atari ST computers"

    game_options = [
        {
            "option": "disk-a",
            "type": "file",
            "label": "Floppy Disk A"
        },
        {
            "option": "disk-b",
            "type": "file",
            "label": "Floppy Disk B"
        }
    ]

    joystick_choices = [
        ('None', 'none'),
        ('Keyboard', 'keys'),
        ('Joystick', 'real')
    ]

    runner_options = [
        {
            "option": "bios_file",
            "type": "file",
            "label": "Bios File (TOS.img)"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        {
            "option": "zoom",
            "type": "bool",
            "label": "Double ST low resolution"
        },
        {
            "option": "borders",
            "type": "bool",
            'label': 'Add borders to display'
        },
        {
            "option": "status",
            "type": "bool",
            'label': 'Display status bar'
        },
        {
            "option": "joy0",
            "type": "choice",
            "label": "Joystick 1",
            "choices": joystick_choices
        },
        {
            "option": "joy1",
            "type": "choice",
            "label": "Joystick 2",
            "choices": joystick_choices
        }
    ]

    def play(self):
        params = [self.executable]
        game_settings = self.settings['game'] or {}
        if self.runner_config.get("fullscreen"):
            params.append("--fullscreen")
        else:
            params.append("--window")

        if self.runner_config.get("zoom"):
            params.append("--zoom 2")
        else:
            params.append("--zoom 1")

        if self.runner_config.get("borders"):
            params.append('--borders true')
        else:
            params.append('--borders false')

        if self.runner_config.get("status"):
            params.append('--statusbar true')
        else:
            params.append('--statusbar false')

        if self.runner_config.get("joy0"):
            params.append("--joy0 " + self.runner_config['joy0'])

        if self.runner_config.get("joy1"):
            params.append("--joy1 " + self.runner_config['joy1'])

        if os.path.exists(self.runner_config.get('bios_file')):
            params.append("--tos " + self.runner_config["bios_file"])
        else:
            return {'error': 'NO_BIOS'}
        diska = game_settings.get('disk-a')
        if not os.path.exists(diska):
            return {'error': 'FILE_NOT_FOUND', 'file': diska}
        params.append("--disk-a \"%s\"" % diska)

        return {"command": params}
