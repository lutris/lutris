# -*- coding: utf-8 -*-
import os
from lutris.runners.wine import wine
from lutris.gui.dialogs import DirectoryDialog
from lutris.config import LutrisConfig


class nulldc(wine):
    """Runner for the Dreamcast emulator NullDC

       Since there is no good Linux emulator out there, we have to use a
       Windows emulator. It runs pretty well.

       NullDC is now OpenSource ! Somebody please port it to Linux.
       The open source NullDC version (1.0.4) doesn't work with wine !

       Download link : http://nulldc.googlecode.com/files/nullDC_104_r50.7z

       Joy2key config:

        joy2key $(xwininfo -root -tree  | grep nullDC | grep -v VMU |\
                awk '{print $1}') \
                -X  -rcfile ~/.joy2keyrc \
                -buttons y a b x c r l r o s -axis Left Right Up Down
    """
    description = "Runs Dreamcast games with nullDC emulator"
    platform = "Sega Dreamcast"
    depends = "wine"
    executable = "nullDC_1.0.3_nommu.exe"
    game_options = [{
        'option': 'iso',
        'type': 'file',
        'name': 'iso',
        'label': 'Disc image'
    }]

    def install(self):
        """Install NullDC"""
        dlg = DirectoryDialog('Where is NullDC located ?')
        config = LutrisConfig(runner=self.__class__.__name__)
        config.runner_config = {'system': {'game_path': dlg.folder}}
        config.save()

    def is_installed(self):
        """Check if NullDC is installed"""
        if not self.check_depends():
            return False
        nulldc_path = self.get_nulldc_path()
        if not nulldc_path or not os.path.exists(nulldc_path):
            return False
        else:
            return True

    def get_nulldc_path(self):
        """ Return the full path for the NullDC executable."""
        # FIXME: return path of nulldc
        return

    def play(self):
        """Run Dreamcast game"""
        # -config ImageReader:DefaultImage="[rompath]/[romfile]"
        path = self.settings['game']['iso']
        path = path.replace("/", "\\")
        path = 'Z:' + path

        command = ["wine", self.get_nulldc_path(),
                   "-config", "ImageReader:DefaultImage=\"%s\"" % path]

        self.check_regedit_keys()  # From parent wine runner
        return {'command': command,
                'joy2key': {'buttons': 'y a b x c r l r o s',
                            'window': 'nullDC',
                            'notwindow': 'VMU'}}
