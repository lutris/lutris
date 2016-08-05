import os
import shutil
from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import QuestionDialog, FileDialog
from lutris.runners.runner import Runner
from lutris.util import system


class pcsxr(Runner):
    human_name = "PCSX-Reloaded"
    description = "PlayStation emulator"
    package = "pcsxr"
    platform = "Playstation"
    runnable_alone = True
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
        },
        {
            'option': 'nogui',
            'type': 'bool',
            'label': "No emulator interface on exit",
            'default': False,
            'help': ("With this option on, hitting the Escape key during "
                     "play will stop the game. Otherwise it pauses the "
                     "emulation and displays PCSX-Reloaded's user interface, "
                     "allowing you to configure the emulator.")
        }
    ]

    def get_executable(self):
        # Lutris provided emulator
        pcsxr_path = os.path.join(settings.RUNNER_DIR, 'pcsxr/bin/pcsxr')
        if os.path.exists(pcsxr_path):
            return pcsxr_path
        # System wide available emulator
        candidates = ('pcsx', 'pcsxr')
        for candidate in candidates:
            executable = system.find_executable(candidate)
            if executable:
                return executable

    def install(self, version=None, downloader=None, callback=None):
        def on_runner_installed(*args):
            bios_path = system.create_folder('~/.pcsxr/bios')
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
                config = LutrisConfig(runner_slug='pcsxr')
                config.raw_runner_config.update({'bios': bios_path})
                config.save()
            if callback:
                callback()
        super(pcsxr, self).install(version, downloader, on_runner_installed)

    def play(self):
        """Run Playstation game."""
        iso = self.game_config.get('iso')
        if not os.path.exists(iso):
            return {'error': 'FILE_NOT_FOUND', 'file': iso}
        command = [self.get_executable()]
        # Options
        if self.runner_config.get('nogui') \
           and os.path.exists(os.path.expanduser("~/.pcsxr")):
            command.append("-nogui")

        command.append("-cdfile")
        command.append(iso)
        command.append("-runcd")
        return {'command': command}
