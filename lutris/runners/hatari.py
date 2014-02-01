""" Runner for Atari ST computers """

from lutris.runners.runner import Runner
import os


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
        """Run Atari ST game"""
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}

        params = [self.executable]

        settings = self.settings['hatari'] or {}
        game_settings = self.settings['game'] or {}
        if "fullscreen" in settings and settings["fullscreen"]:
            params.append("--fullscreen")
        else:
            params.append("--window")

        if "zoom" in settings and settings["zoom"]:
            params.append("--zoom 2")
        else:
            params.append("--zoom 1")

        if 'borders' in settings and settings["borders"]:
            params.append('--borders true')
        else:
            params.append('--borders false')

        if 'status' in settings and settings["status"]:
            params.append('--statusbar true')
        else:
            params.append('--statusbar false')

        if "joy1" in settings:
            params.append("--joy0 " + settings['joy0'])

        if "joy2" in settings:
            params.append("--joy1 " + settings['joy1'])

        if "bios_file" in settings:
            if os.path.exists(settings['bios_file']):
                params.append("--tos " + settings["bios_file"])
            else:
                return {
                    'error': 'FILE_NOT_FOUND',
                    'file': settings['bios_file']
                }
        else:
            return {'error': 'NO_BIOS'}
        diska = game_settings.get('disk-a')
        if not os.path.exists(diska):
            return {'error': 'FILE_NOT_FOUND', 'file': diska}
        params.append("--disk-a \"%s\"" % diska)

        return {"command": params}
