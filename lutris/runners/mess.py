import os
from lutris import settings
from lutris.runners.runner import Runner


class mess(Runner):
    """ Multi-system (consoles and computers) emulator """
    name = "MESS"
    platform = 'multi-platform'
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
            'help': ("The game data, commonly called a ROM image.")
        },
        {
            'option': 'machine',
            'type': 'choice',
            'label': "Machine",
            'choices': [
                ("Amstrad CPC 464", 'cpc464'),
                ("Amstrad CPC 6128", 'cpc6128'),
                ("Commodore 64", 'c64'),
                ("ZX Spectrum", 'spectrum'),
                ("ZX Spectrum 128", 'spec128'),
            ],
            'help': ("The emulated machine.")
        },
        {
            'option': 'device',
            'type': 'choice',
            'label': "Storage type",
            'choices': [
                ("Floppy disk", 'flop1'),
                ("Cassette (tape)", 'cass'),
                ("Cartridge", 'cart'),
                ("Snapshot", 'snapshot'),
                ("Quickload", 'quickload'),
            ]
        }
    ]
    runner_options = [
        {
            'option': 'rompath',
            'type': 'directory_chooser',
            'label': "BIOS path",
            'help': ("Choose the folder containing MESS bios files.\n"
                     "These files contain code from the original hardware "
                     "necessary to the emulation.")
        }
    ]

    tarballs = {
        "x64": "mess-0.154-x86_64.tar.gz",
    }

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, "mess/mess")

    def play(self):
        rompath = self.runner_config.get('rompath') or ''
        if not os.path.exists(rompath):
            return {'error': 'NO_BIOS'}
        machine = self.game_config.get('machine')
        if not machine:
            return {'error': 'INCOMPLETE_CONFIG'}
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        device = self.game_config.get('device')
        command = [self.get_executable(),
                   '-rompath', "\"%s\"" % rompath, machine,
                   '-' + device, "\"%s\"" % rom]
        return {'command': command}
