import os
import shutil
from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import QuestionDialog, FileDialog
from lutris.runners.runner import Runner


class hatari(Runner):
    """Atari ST computers"""
    human_name = "Hatari"
    platform = "Atari ST computers"

    game_options = [
        {
            "option": "disk-a",
            "type": "file",
            "label": "Floppy Disk A",
            'help': ("Hatari supports floppy disk images in the following "
                     "formats: ST, DIM, MSA, STX, IPF, RAW and CRT. The last "
                     "three require the caps library (capslib). ZIP is "
                     "supported, you don't need to uncompress the file.")
        },
        {
            "option": "disk-b",
            "type": "file",
            "label": "Floppy Disk B",
            'help': ("Hatari supports floppy disk images in the following "
                     "formats: ST, DIM, MSA, STX, IPF, RAW and CRT. The last "
                     "three require the caps library (capslib). ZIP is "
                     "supported, you don't need to uncompress the file.")
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
            "label": "Bios file (TOS)",
            'help': ("TOS is the operating system of the Atari ST "
                     "and is necessary to run applications with the best "
                     "fidelity, minimizing risks of issues.\n"
                     "TOS 1.02 is recommended for games.")
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            'default': False,
        },
        {
            "option": "zoom",
            "type": "bool",
            "label": "Scale up display by 2 (Atari ST/STE)",
            'default': True,
            'help': ("Double the screen size in windowed mode.")
        },
        {
            "option": "borders",
            "type": "bool",
            'label': 'Add borders to display',
            'default': False,
            'help': ("Useful for some games and demos using the overscan "
                     "technique. The Atari ST displayed borders around the "
                     "screen because it was not powerful enough to display "
                     "graphics in fullscreen. But people from the demo scene "
                     "were able to remove them and some games made use of "
                     "this technique.")
        },
        {
            "option": "status",
            "type": "bool",
            'label': 'Display status bar',
            'default': False,
            'help': ("Displays a status bar with some useful information, "
                     "like green leds lighting up when the floppy disks are "
                     "read.")
        },
        {
            "option": "joy0",
            "type": "choice",
            "label": "Joystick 1",
            "choices": joystick_choices,
            'default': 'none',
        },
        {
            "option": "joy1",
            "type": "choice",
            "label": "Joystick 2",
            "choices": joystick_choices,
            'default': 'none',
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
            config = LutrisConfig(runner_slug='hatari')
            config.runner_level = {'hatari': {'bios_file': bios_path}}
            config.save()
        return True

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'hatari/bin/hatari')

    def play(self):
        params = [self.get_executable()]
        if self.runner_config.get("fullscreen"):
            params.append("--fullscreen")
        else:
            params.append("--window")

        params.append("--zoom")
        if self.runner_config.get("zoom"):
            params.append("2")
        else:
            params.append("1")

        params.append('--borders')
        if self.runner_config.get("borders"):
            params.append('true')
        else:
            params.append('false')

        params.append('--statusbar')
        if self.runner_config.get("status"):
            params.append('true')
        else:
            params.append('false')

        if self.runner_config.get("joy0"):
            params.append("--joy0")
            params.append(self.runner_config['joy0'])

        if self.runner_config.get("joy1"):
            params.append("--joy1")
            params.append(self.runner_config['joy1'])

        if os.path.exists(self.runner_config.get('bios_file', '')):
            params.append('--tos')
            params.append(self.runner_config["bios_file"])
        else:
            return {'error': 'NO_BIOS'}
        diska = self.game_config.get('disk-a')
        if not os.path.exists(diska):
            return {'error': 'FILE_NOT_FOUND', 'file': diska}
        params.append("--disk-a")
        params.append(diska)

        return {"command": params}
