import os
from lutris import settings
from lutris.runners.runner import Runner


class vice(Runner):
    """ Commodore Emulator """
    platform = "Commodore 64"

    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": "ROM file",
            'help': ("The game data, commonly called a ROM image.\n"
                     "Supported formats: X64, D64, G64, P64, D67, D71, D81, "
                     "D80, D82, D1M, D2M, D4M, T46, P00 and CRT.")
    }]

    runner_options = [
        {
            "option": "joy",
            "type": "bool",
            "label": "Use joysticks"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        {
            "option": "double",
            "type": "bool",
            "label": "Scale up display by 2"
        },
        {
            "option": "machine",
            "type": "choice",
            "label": "Machine",
            "choices": [
                ("C64", "c64"),
                ("C128", "c128"),
                ("vic20", "vic20"),
                ("PET", "pet"),
                ("Plus/4", "plus4"),
                ("CMB-II", "cbmii")
            ],
            "default": "c64"
        }
    ]

    tarballs = {
        "x64": "vice-2.4-x86_64.tar.gz"
    }

    def get_executable(self, machine=None):
        if not machine:
            machine = "c64"
        executables = {
            "c64": "x64",
            "c128": "x128",
            "vic20": "xvic",
            "pet": "xpet",
            "plus4": "xplus4",
            "cmbii": "xcbm2"
        }
        try:
            executable = executables[machine]
        except KeyError:
            raise ValueError("Invalid machine '%s'" % machine)
        return os.path.join(settings.RUNNER_DIR, "vice/bin/%s" % executable)

    def get_roms_path(self, machine=None):
        if not machine:
            machine = "c64"
        paths = {
            "c64": "C64",
            "c128": "C128",
            "vic20": "VIC20",
            "pet": "PET",
            "plus4": "PLUS4",
            "cmbii": "CBM-II"
        }
        root_dir = os.path.dirname(os.path.dirname(self.get_executable()))
        return os.path.join(root_dir, 'lib64/vice', paths[machine])

    def play(self):
        machine = self.runner_config.get("machine")
        params = [self.get_executable(machine),
                  "-chdir", self.get_roms_path(machine)]
        if self.runner_config.get("fullscreen"):
            params.append("-fullscreen")
        if self.runner_config.get("double"):
            params.append("-VICIIdsize")
        if self.runner_config.get("joy"):
            params += ["-joydev2", "4", "-joydev1", "5"]
        params.append("\"%s\"" % self.settings['game']['main_file'])
        return {'command': params}
