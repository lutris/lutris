import os
from lutris.runners.runner import Runner


class jzintv(Runner):
    human_name = "jzIntv"
    description = "Intellivision Emulator"
    platforms = ["Intellivision"]
    runner_executable = 'jzintv/bin/jzintv'
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label': "ROM file",
        'default_path': 'game_path',
        'help': ("The game data, commonly called a ROM image. \n"
                 "Supported rom formats: .rom, .bin+.cfg, .int, .itv \n"
                 "The file extension must be lower-case.")
    }]
    runner_options = [
        {
            "option": "bios_path",
            "type": "directory_chooser",
            "label": "Bios location",
            'help': ("Choose the folder containing the Intellivision bios "
                     "files (exec.bin and grom.bin).\n"
                     "These files contain code from the original hardware "
                     "necessary to the emulation.")
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        # Adds the resoluton menu chooser
        # jzintv has some resolution presets with the command -z
        # going from -z0 to -z7. Some details on those presets
        # are unknown and just speculated
        {
            "option": "resolution",
            "type": "choice",
            "label": "Resolution",
            "choices": (
                ("320 x 200 (default)", "0"),
                ("640 x 480", "1"),
                ("800 x 600", "2"),
                ("1024 x 768", "3"),
                ("1152 x 864 ?", "4"),
                ("1280 x 1024 ?", "5"),
                ("1600 x 1200 ?", "6"),
                ("1920 x 1080 ?", "7"),
            )
        }
        ############################################################
    ]

    def play(self):
        """Run Intellivision game"""
        arguments = [self.get_executable()]
        
        # Treatment of the choosen resolution
        selected_resolution = self.runner_config.get("resolution")
        if selected_resolution:
            arguments = arguments + ["-z%s" % selected_resolution]
        #####################################
        
        if self.runner_config.get("fullscreen"):
            arguments = arguments + ["-f"]
        bios_path = self.runner_config.get("bios_path", '')
        if os.path.exists(bios_path):
            arguments.append("--execimg=%s/exec.bin" % bios_path)
            arguments.append("--gromimg=%s/grom.bin" % bios_path)
        else:
            return {'error': 'NO_BIOS'}
        rom_path = self.game_config.get('main_file') or ''
        if not os.path.exists(rom_path):
            return {'error': 'FILE_NOT_FOUND', 'file': rom_path}
        romdir = os.path.dirname(rom_path)
        romfile = os.path.basename(rom_path)
        arguments += ["--rom-path=%s/" % romdir]
        arguments += [romfile]
        return {'command': arguments}
