import os
import subprocess

from lutris.runners.runner import Runner
from lutris.gui.dialogs import DownloadDialog
from lutris.settings import CACHE_DIR


class gens(Runner):
    """Runner for Sega Genesis games"""
    executable = 'gens'
    platform = 'Sega Genesis'
    description = 'Sega Genesis emulator.'
    tarballs = {
        'i386': 'gens-2.16.7-i386.tar.gz',
        'x64': 'gens-2.16.7-i386.tar.gz',
    }
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label':  'Rom File'
    }]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': True
        },
        {
            'option': 'quickexit',
            'type': 'bool',
            'label': 'Exit emulator with Esc',
            'default': True
        }
    ]

    def install(self):
        """Downloads deb package and installs it"""
        dest = os.path.join(CACHE_DIR, 'gens-gs.deb')
        package = 'http://segaretro.org/images/7/75/Gens_2.16.7_i386.deb'
        dialog = DownloadDialog(package, dest)
        dialog.run()
        subprocess.Popen(["software-center", dest],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)

    def play(self):
        """ Run the game """
        arguments = [self.executable]
        if self.runner_config.get('fullscreen', True):
            arguments.append('--fs')
        else:
            arguments.append('--window')
        if self.runner_config.get('quickexit', True):
            arguments.append('--quickexit')
        rom = self.settings['game']['main_file']
        plugins_dir = os.path.join(os.path.expanduser('~'), '.gens/plugins')
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append("--game \"%s\"" % rom)
        return {"command": arguments}
