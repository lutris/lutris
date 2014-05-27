# -*- coding: utf-8 -*-
""" Runner for Gamecube and Wii """
from lutris.runners.runner import Runner
from lutris.gui.dialogs import NoticeDialog


class dolphin(Runner):
    """Runner for the Gamecube / Wii emulator Dolphin

    Code repository: http://code.google.com/p/dolphin-emu/
    Download link : http://dolphin.jcf129.com/dolphin-2.0.i686.tar.bz2
    ppa : ppa:glennric/dolphin-emu
    """
    package = "dolphin-emu"
    executable = "dolphin"
    platform = "Gamecube, Wii"
    description = "Emulator for Nintendo Gamecube and Wii games"
    game_options = []
    runner_options = []

    def install(self):
        """Run Gamecube or Wii game"""
        NoticeDialog(
            'Please activate the Dolphin PPA reposiories in order to '
            'install Dolphin'
        )
        super(dolphin, self).install()
