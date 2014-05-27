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
        'label': 'Disc image'
    }]

    def is_installed(self):
        """Check if NullDC is installed"""
        if not self.check_depends():
            return False
        nulldc_path = self.get_executable()
        return nulldc_path and os.path.exists(nulldc_path)

    def get_executable(self):
        """ Return the full path for the NullDC executable."""
        return os.path.join(settings.RUNNER_DIR,
                            'nulldc/nullDC_1.0.3_nommu.exe')

    def play(self):
        """Run Dreamcast game"""
        path = self.settings['game'].get('iso')
        path = path.replace("/", "\\")
        path = 'Z:' + path

        command = [
            "wine", self.get_executable(),
            "-config", "ImageReader:DefaultImage=\"%s\"" % path
        ]
        return {
            'command': command,
        }
        #     'joy2key': {
        #         'buttons': 'y a b x c r l r o s',
        #         'window': 'nullDC',
        #         'notwindow': 'VMU'
        #     }
        # }
