import os
from lutris.runners.runner import Runner


class sdlmess(Runner):
    """ Multi-system (consoles and computers) emulator """
    executable = 'mess'
    platform = 'multi-platform'
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'Rom file'
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
            ]
        },
        {
            'option': 'device',
            'type': 'choice',
            'label': "Storage type",
            'choices': [
                ("Floppy disk", 'flop1'),
                ("Cassette", 'cass'),
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
            'label': "BIOS path"
        }
    ]

    def play(self):
        rompath = self.settings['sdlmess'].get('rompath')
        if not os.path.exists(rompath):
            return {'error': 'FILE_NOT_FOUND', 'file': rompath}
        machine = self.settings['game'].get('machine')
        if not machine:
            return {'error': 'INCOMPLETE_CONFIG'}
        rom = self.settings['game'].get('main_file')
        if not os.path.exists(rompath):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        device = self.settings['game'].get('device')
        command = [self.executable,
                   '-rompath', "\"%s\"" % rompath, machine,
                   '-' + device, "\"%s\"" % rom]
        return {'command': command}
