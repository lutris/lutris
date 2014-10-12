import os
import shutil
from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import QuestionDialog, FileDialog
from lutris.runners.runner import Runner
from lutris.util.system import find_executable


class pcsxr(Runner):
    """PlayStation emulator"""
    package = "pcsxr"
    platform = "Playstation"
    game_options = [
        {
            "option": "iso",
            "type": "file",
            "label": "Disk image",
            "default_path": "game_path",
            'help': ("An ISO file containing the game data.")
        }
    ]
    runner_options = [
        {
            "option": "bios",
            "type": "file",
            "label": "Bios file",
            'help': ("The Playstation bios file.\n"
                     "This file contains code from the original hardware "
                     "necessary to the emulation.")
        }
    ]
    tarballs = {
        'x64': 'pcsxr-x86_64-1.9.95.tar.gz',
    }

    def get_executable(self):
        # Lutris provided emulator
        pcsxr_path = os.path.join(settings.RUNNER_DIR, 'pcsxr/bin/pcsxr')
        if os.path.exists(pcsxr_path):
            return pcsxr_path
        # System wide available emulator
        candidates = ('pcsx', 'pcsxr')
        for candidate in candidates:
            executable = find_executable(candidate)
            if executable:
                return executable

    def install(self):
        success = super(pcsxr, self).install()
        if not success:
            return False
        config_path = os.path.expanduser('~/.pcsxr')
        if not os.path.exists(config_path):
            os.makedirs(config_path)

        # Bios
        bios_path = os.path.expanduser('~/.pcsxr/bios')
        if not os.path.exists(bios_path):
            os.makedirs(bios_path)
        dlg = QuestionDialog({
            'question': ("Do you want to select a Playstation BIOS file?\n\n"
                         "The BIOS is the core code running the machine.\n"
                         "PCSX-Reloaded includes an emulated BIOS, but it is "
                         "still incomplete. \n"
                         "Using an original BIOS avoids some bugs and reduced "
                         "compatibility \n"
                         "with some games."),
            'title': "Use BIOS file?",
        })
        if dlg.result == dlg.YES:
            bios_dlg = FileDialog("Select a BIOS file")
            bios_src = bios_dlg.filename
            shutil.copy(bios_src, bios_path)
            # Save bios in config
            bios_path = os.path.join(bios_path, os.path.basename(bios_src))
            runner_config = LutrisConfig(runner='pcsxr')
            runner_config.config_type = 'runner'
            runner_config.runner_config = {'pcsxr': {'bios': bios_path}}
            runner_config.save()
        return True

    def play(self):
        """Run Playstation game"""
        iso = self.settings["game"].get("iso")
        command = [self.get_executable(),
                   " -nogui -cdfile \"" + iso + "\" -runcd"]
        return {'command': command}
