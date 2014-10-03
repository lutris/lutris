import os
import shutil
from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import QuestionDialog, FileDialog
from lutris.runners.runner import Runner


class hatari(Runner):
    """Atari ST computers"""
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

    tarballs = {
        "x64": "hatari-1.8.0-x86_64.tar.gz",
    }

    def install(self):
        success = super(hatari, self).install()
        if not success:
            return False
        config_path = os.path.expanduser('~/.hatari')
        if not os.path.exists(config_path):
            os.makedirs(config_path)
        bios_path = os.path.expanduser('~/.hatari/bios')
        if not os.path.exists(bios_path):
            os.makedirs(bios_path)
        dlg = QuestionDialog({
            'question': "Do you want to select an Atari ST BIOS file?",
            'title': "Use BIOS file?",
        })
        if dlg.result == dlg.YES:
            bios_dlg = FileDialog("Select a BIOS file")
            bios_filename = bios_dlg.filename
            shutil.copy(bios_filename, bios_path)
            bios_path = os.path.join(bios_path, os.path.basename(bios_filename))
            runner_config = LutrisConfig(runner='hatari')
            runner_config.config_type = 'runner'
            runner_config.runner_config = {'hatari': {'bios_file': bios_path}}
            runner_config.save()
        return True

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'hatari/bin/hatari')

    def play(self):
        params = [self.get_executable()]
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

        if os.path.exists(self.runner_config.get('bios_file', '')):
            params.append("--tos " + self.runner_config["bios_file"])
        else:
            return {'error': 'NO_BIOS'}
        diska = game_settings.get('disk-a')
        if not os.path.exists(diska):
            return {'error': 'FILE_NOT_FOUND', 'file': diska}
        params.append("--disk-a \"%s\"" % diska)

        return {"command": params}
