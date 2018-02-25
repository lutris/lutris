import shutil
import os
from lutris.runners.runner import Runner
from lutris.gui.dialogs import QuestionDialog, FileDialog
from lutris import settings



class redream(Runner):
    human_name = "Redream"
    description = "Sega Dreamcast emulator"
    platforms = ['Sega Dreamcast']
    runner_executable = 'redream/redream'
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": 'Disc image file',
            "help": ("Game data file\n"
                     "Supported formats: GDI, CDI, CHD")
        }
    ]
    runner_options = [
        {
            'option': 'fs',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': False,
        },
        {
            'option': 'ar',
            'type': 'choice',
            'label': 'Aspect Ratio',
            'choices': [('4:3', '4:3'),
                        ('Stretch', 'stretch')],
            'default': '4:3'
        },
        {
            'option': 'region',
            'type': 'choice',
            'label': 'Region',
            'choices': [('USA', 'usa'),
                        ('Europe', 'europe'),
                        ('Japan', 'japan')],
            'default': 'usa'
        },
        {
            'option': 'language',
            'type': 'choice',
            'label': 'System Language',
            'choices': [('English', 'english'),
                        ('German', 'german'),
                        ('French', 'french'),
                        ('Spanish', 'spanish'),
                        ('Italian', 'italian'),
                        ('Japanese', 'japanese')],
            'default': 'english'
        },
        {
            'option': 'broadcast',
            'type': 'choice',
            'label': 'Television System',
            'choices': [('NTSC', 'ntsc'),
                        ('PAL', 'pal'),
                        ('PAL-M (Brazil)', 'pal_m'),
                        ('PAL-N (Argentina, Paraguay, Uruguay)', 'pal_n')],
            'default': 'ntsc'
        },
        {
            'option': 'time_sync',
            'type': 'choice',
            'label': 'Time Sync',
            'choices': [('Audio and video', 'audio and video'),
                        ('Audio', 'audio'),
                        ('Video', 'video'),
                        ('None', 'none')],
            'default': 'audio and video',
            'advanced': True
        },
        {
            'option': 'int_res',
            'type': 'choice',
            'label': 'Internal Video Resolution Scale',
            'choices': [('×1', '1'),
                        ('×2', '2'),
                        ('×3', '3'),
                        ('×4', '4'),
                        ('×5', '5'),
                        ('×6', '6'),
                        ('×7', '7'),
                        ('×8', '8')],
            'default': '2',
            'advanced': True,
            'help': 'Only available in premium version.'
        }
    ]

    def install(self, version=None, downloader=None, callback=None):
        def on_runner_installed(*args):
            dlg = QuestionDialog({
                'question': "Do you want to select a premium license file?",
                'title': "Use premium version?",
            })
            if dlg.result == dlg.YES:
                license_dlg = FileDialog("Select a license file")
                license_filename = license_dlg.filename
                if not license_filename:
                    return
                shutil.copy(license_filename, os.path.join(settings.RUNNER_DIR, 'redream'))
        super(redream, self).install(version=version,
                                     downloader=downloader,
                                     callback=on_runner_installed)

    def play(self):
        command = [self.get_executable()]

        if self.runner_config.get('fs') is True:
            command.append('--fullscreen=1')
        else:
            command.append('--fullscreen=0')

        if self.runner_config.get('ar'):
            command.append('--aspect=' + self.runner_config.get('ar'))

        if self.runner_config.get('region'):
            command.append('--region=' + self.runner_config.get('region'))

        if self.runner_config.get('language'):
            command.append('--language=' + self.runner_config.get('language'))

        if self.runner_config.get('broadcast'):
            command.append('--broadcast=' + self.runner_config.get('broadcast'))

        if self.runner_config.get('time_sync'):
            command.append('--time_sync=' + self.runner_config.get('time_sync'))

        if self.runner_config.get('int_res'):
            command.append('--res=' + self.runner_config.get('int_res'))

        command.append(self.game_config.get('main_file'))

        return {'command': command}
