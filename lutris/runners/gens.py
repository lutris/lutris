""" Runner for Sega Genesis games """
import subprocess

import os
from os.path import expanduser

from lutris.runners.runner import Runner
from lutris.gui.dialogs import DownloadDialog
from lutris.settings import CACHE_DIR


class gens(Runner):
    """Runner for Sega Genesis games"""
    def __init__(self, settings=None):
        """Constructor"""
        super(gens, self).__init__()
        self.package = 'gens-gs'
        self.executable = 'gens'
        self.platform = 'Sega Genesis'
        self.description = 'Sega Genesis emulator.'
        self.game_options = [{
            'option': 'rom',
            'type': 'file',
            'label':  'Rom File'
        }]
        self.runner_options = [
            {
                'option': 'fullscreen',
                'type': 'bool',
                'label': 'Fullscreen'
            },
            {
                'option': 'quickexit',
                'type': 'bool',
                'label': 'Exit emulator with Esc'
            }
        ]
        if settings:
            if 'fullscreen' in settings['gens']:
                if settings['gens']['fullscreen']:
                    self.arguments = self.arguments + ['--fs']
                else:
                    self.arguments = self.arguments + ['--window']
            if 'quickexit' in settings['gens']:
                if settings['gens']['quickexit']:
                    self.arguments = self.arguments + ['--quickexit']
            if 'rom' in settings['game']:
                self.rom = settings['game']['rom']

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
        plugins_dir = os.path.join(os.path.expanduser('~'), '.gens/plugins')
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        if not os.path.exists(self.rom):
            return {'error': 'FILE_NOT_FOUND', 'file': self.rom}
        arguments = ["--game \"%s\"" % self.rom]
        command = [self.executable] + arguments
        return {"command": command}
