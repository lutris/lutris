# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner


class nulldc(Runner):
    """Sega Dreamcast emulator"""

    #  Since there is no good Linux emulator out there, we have to use a
    #  Windows emulator. It runs pretty well.
    #  NullDC is now OpenSource ! Somebody please port it to Linux.
    #  The open source NullDC version (1.0.4) doesn't work with wine !
    #  Download link : http://nulldc.googlecode.com/files/nullDC_104_r50.7z
    #
    #  Joy2key config:
    #   joy2key $(xwininfo -root -tree  | grep nullDC | grep -v VMU |\
    #           awk '{print $1}') \
    #           -X  -rcfile ~/.joy2keyrc \
    #           -buttons y a b x c r l r o s -axis Left Right Up Down

    human_name = "NullDC"
    platform = "Sega Dreamcast"
    depends = "wine"

    tarballs = {
        'i386': 'nulldc-1.0.3.tar.gz',
        'x64': 'nulldc-1.0.3.tar.gz',
    }

    game_options = [{
        'option': 'iso',
        'type': 'file',
        'name': 'iso',
        'label': 'Disc image file',
        'help': ("The game data.\n"
                 "Supported formats: ISO, CDI")
    }]

    runner_options = [{
        'option': 'joy2key',
        'type': 'bool',
        'label': "Simulate joypad with joy2key",
        'help': ("Requires joy2key installed on your system.")
    }]

    def is_installed(self):
        """Check if NullDC is installed"""
        wine_installed = super(nulldc, self).is_installed()
        if not wine_installed:
            return False
        nulldc_path = self.get_executable()
        return nulldc_path and os.path.exists(nulldc_path)

    def get_executable(self):
        """ Return the full path for the NullDC executable."""
        return os.path.join(settings.RUNNER_DIR,
                            'nulldc/nullDC_1.0.3_nommu.exe')

    def play(self):
        """Run Dreamcast game"""
        path = self.game_config.get('iso')
        path = path.replace("/", "\\")
        path = 'Z:' + path

        command = [
            "wine", self.get_executable(),
            "-config", "ImageReader:DefaultImage=\"%s\"" % path
        ]
        launch_arguments = {'command': command}
        if self.runner_config.get('joy2key'):
            launch_arguments['joy2key'] = {
                'buttons': 'z c x v m b Shift_R Shift_R',
                'window': 'nullDC',
                'notwindow': 'VMU'
            }
        return launch_arguments
