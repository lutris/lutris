import os
from lutris import settings
from lutris.util import system
from lutris.util.log import logger
from lutris.runners.runner import Runner


class vice(Runner):
    description = "Commodore Emulator"
    human_name = "Vice"
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
            "label": "Use joysticks",
            'default': False,
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            'default': False,
        },
        {
            "option": "double",
            "type": "bool",
            "label": "Scale up display by 2",
            'default': True,
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

    def install(self, version=None, downloader=None, callback=None):
        def on_runner_installed(*args):
            config_path = system.create_folder('~/.vice')
            lib_dir = os.path.join(settings.RUNNER_DIR, 'vice/lib/vice')
            if not os.path.exists(lib_dir):
                lib_dir = os.path.join(settings.RUNNER_DIR, 'vice/lib64/vice')
            if not os.path.exists(lib_dir):
                logger.error('Missing lib folder in the Vice runner')
            else:
                system.merge_folders(lib_dir, config_path)
            if callback:
                callback()

        super(vice, self).install(version, downloader, on_runner_installed)

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

    def get_option_prefix(self, machine):
        prefixes = {
            'c64': 'VICII',
            'c128': 'VICII',
            'vic20': 'VIC',
            'pet': 'CRTC',
            'plus4': 'TED',
            'cmbii': 'CRTC'
        }
        return prefixes[machine]

    def get_joydevs(self, machine):
        joydevs = {
            'c64': 2,
            'c128': 2,
            'vic20': 1,
            'pet': 0,
            'plus4': 2,
            'cmbii': 0
        }
        return joydevs[machine]

    def play(self):
        machine = self.runner_config.get("machine")

        rom = self.game_config.get('main_file')
        if not rom:
            return {'error': 'CUSTOM', 'text': 'No rom provided'}
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}

        params = [self.get_executable(machine)]
        rom_dir = os.path.dirname(rom)
        params.append('-chdir')
        params.append(rom_dir)
        option_prefix = self.get_option_prefix(machine)
        if self.runner_config.get("fullscreen"):
            params.append('-{}full'.format(option_prefix))
        if self.runner_config.get("double"):
            params.append("-{}dsize".format(option_prefix))
        if self.runner_config.get("joy"):
            for dev in range(self.get_joydevs(machine)):
                params += ["-joydev{}".format(dev + 1), "4"]
        if rom.endswith('.crt'):
            params.append('-cartgeneric')
        params.append(rom)
        return {'command': params}
