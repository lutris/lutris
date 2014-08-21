import os
import shutil
from lutris import settings
from lutris.gui.dialogs import QuestionDialog, FileDialog
from lutris.runners.runner import Runner
from lutris.util.system import find_executable


class pcsxr(Runner):
    """PlayStation emulator"""
    package = "pcsxr"
    platform = "Playstation"
    game_options = [{
        "option": "iso",
        "type": "file",
        "label": "iso",
        "default_path": "game_path",
    }]
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
        bios_path = os.path.expanduser('~/.pcsxr/bios')
        if not os.path.exists(bios_path):
            os.makedirs(bios_path)
        dlg = QuestionDialog({
            'question': "Do you want to select a Playstation BIOS file?",
            'title': "Use BIOS file?",
        })
        if dlg.result == dlg.YES:
            bios_dlg = FileDialog("Select a BIOS file")
            bios_filename = bios_dlg.filename
            shutil.copy(bios_filename, bios_path)
        return True

    def play(self):
        """Run Playstation game"""
        iso = self.settings["game"].get("iso")
        command = [self.get_executable(),
                   " -nogui -cdfile \"" + iso + "\" -runcd"]
        return {'command': command}
