import os
from lutris import settings
from lutris.util.log import logger
from lutris.runners.runner import Runner
from lutris.util import system


class mess(Runner):
    human_name = "MESS"
    description = "Multi-system (consoles and computers) emulator"
    # TODO: A lot of platforms/machines are missing
    platforms = (
        'Acorn Atom',
        'Adventure Vision',
        'Amstrad CPC 464',
        'Amstrad CPC 6128',
        'Amstrad GX4000',
        'Apple I',
        'Apple II',
        'Apple IIGS',
        'Arcadia 2001',
        'Bally Professional Arcade',
        'BBC Micro',
        'Casio PV-1000',
        'Casio PV-2000',
        'Chintendo Vii',
        'Coleco Adam',
        'Commodore 64',
        'Creatronic Mega Duck',
        'DEC PDP-1',
        'Epoch Game Pocket Computer',
        'Epoch Super Cassette Vision',
        'Fairchild Channel F',
        'Fujitsu FM 7',
        'Fujitsu FM Towns',
        'Funtech Super ACan',
        'Game.com',
        'Hartung Game Master',
        'IBM PCjr',
        'Intellivision',
        'Interton VC 4000',
        'Matra Alice',
        'Mattel Aquarius',
        'Memotech MTX',
        'Milton Bradley MicroVision',
        'NEC PC-8801',
        'NEC PC-88VA',
        'RCA Studio II',
        'Sam Coupe',
        'SEGA Computer 3000',
        'Sega Pico',
        'Sega SG-1000',
        'Sharp MZ-2500',
        'Sharp MZ-700',
        'Sharp X1',
        'Sinclair ZX Spectrum',
        'Sinclair ZX Spectrum 128',
        'Sony SMC777',
        'Spectravision SVI-318',
        'Tatung Einstein',
        'Thomson MO5',
        'Thomson MO6',
        'Tomy Tutor',
        'TRS-80 Color Computer',
        'Videopac Plus G7400',
        'VTech CreatiVision',
        'Watara Supervision',
    )
    machine_choices = [
        ("Acorn Atom", 'atom'),
        ("Adventure Vision", 'advision'),
        ("Amstrad CPC 464", 'cpc464'),
        ("Amstrad CPC 6128", 'cpc6128'),
        ("Amstrad GX4000", 'gx4000'),
        ("Apple I", 'apple1'),
        ("Apple II", 'apple2ee'),
        ("Apple IIGS", 'apple2gs'),
        ("Arcadia 2001", 'arcadia'),
        ("Bally Professional Arcade", 'astrocde'),
        ("BBC Micro", 'bbcb'),
        ("Casio PV-1000", 'pv1000'),
        ("Casio PV-2000", 'pv2000'),
        ("Chintendo Vii", 'vii'),
        ("Coleco Adam", 'adam'),
        ("Commodore 64", 'c64'),
        ("Creatronic Mega Duck", 'megaduck'),
        ("DEC PDP-1", 'pdp1'),
        ("Epoch Game Pocket Computer", 'gamepock'),
        ("Epoch Super Cassette Vision", 'scv'),
        ("Fairchild Channel F", 'channelf'),
        ("Fujitsu FM 7", 'fm7'),
        ("Fujitsu FM Towns", 'fmtowns'),
        ("Funtech Super A'Can", 'supracan'),
        ("Game.com", 'gamecom'),
        ("Hartung Game Master", 'gmaster'),
        ("IBM PCjr", 'ibmpcjr'),
        ("Intellivision", 'intv'),
        ("Interton VC 4000", 'vc4000'),
        ("Matra Alice", 'alice90'),
        ("Mattel Aquarius", 'aquarius'),
        ("Memotech MTX", 'mtx'),
        ("Milton Bradley MicroVision", 'microvision'),
        ("NEC PC-8801", 'pc8801'),
        ("NEC PC-88VA", 'pc88va'),
        ("RCA Studio II", 'studio2'),
        ("Sam Coupe", 'samcoupe'),
        ("SEGA Computer 3000", 'sc3000'),
        ("Sega Pico", 'pico'),
        ("Sega SG-1000", 'sg1000'),
        ("Sharp MZ-2500", 'mz2500'),
        ("Sharp MZ-700", 'mz700'),
        ("Sharp X1", 'x1'),
        ("ZX Spectrum", 'spectrum'),
        ("ZX Spectrum 128", 'spec128'),
        ("Sony SMC777", 'smc777'),
        ("Spectravision SVI-318", 'svi318'),
        ("Tatung Einstein", 'einstein'),
        ("Thomson MO5", 'mo5'),
        ("Thomson MO6", 'mo6'),
        ("Tomy Tutor", 'tutor'),
        ("TRS-80 Color Computer", 'coco'),
        ("Videopac Plus G7400", 'g7400'),
        ("VTech CreatiVision", 'crvision'),
        ("Watara Supervision", 'svision'),
    ]
    runner_executable = "mess/mess"
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
            'help': "The game data, commonly called a ROM image."
        },
        {
            'option': 'machine',
            'type': 'choice_with_entry',
            'label': "Machine",
            'choices': machine_choices,
            'help': "The emulated machine."
        },
        {
            'option': 'device',
            'type': 'choice_with_entry',
            'label': "Storage type",
            'choices': [
                ("Floppy disk", 'flop'),
                ("Floppy drive 1", 'flop1'),
                ("Floppy drive 2", 'flop2'),
                ("Floppy drive 3", 'flop3'),
                ("Floppy drive 4", 'flop4'),
                ("Cassette (tape)", 'cass'),
                ("Cassette 1 (tape)", 'cass1'),
                ("Cassette 2 (tape)", 'cass2'),
                ("Cartridge", 'cart'),
                ("Cartridge 1", 'cart1'),
                ("Cartridge 2", 'cart2'),
                ("Cartridge 3", 'cart3'),
                ("Cartridge 4", 'cart4'),
                ("Snapshot", 'snapshot'),
                ("Hard Disk", 'hard'),
                ("Hard Disk 1", 'hard1'),
                ("Hard Disk 2", 'hard2'),
                ("CDROM", 'cdrm'),
                ("CDROM 1", 'cdrm1'),
                ("CDROM 2", 'cdrm2'),
                ("Snapshot", 'dump'),
                ("Quickload", 'quickload'),
                ("Memory Card", 'memc'),
                ("Cylinder", 'cyln'),
                ("Punch Tape 1", 'ptap1'),
                ("Punch Tape 2", 'ptap2'),
                ("Print Out", 'prin'),
                ("Print Out", 'prin'),

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
        },
        {
            'option': 'uimodekey',
            'type': 'choice_with_entry',
            'label': 'Menu mode key',
            'choices': [
                ('Scroll Lock', 'SCRLOCK'),
                ('Num Lock', 'NUMLOCK'),
                ('Caps Lock', 'CAPSLOCK'),
                ('Menu', 'MENU'),
                ('Right Control', 'RCONTROL'),
                ('Left Control', 'LCONTROL'),
                ('Right Alt', 'RALT'),
                ('Left Alt', 'LALT'),
                ('Right Super', 'RWIN'),
                ('Left Super', 'LWIN'),
            ],
            'help': 'Key to switch between Full Keyboard Mode and Partial Keyboard Mode (default: Scroll Lock)'
        }
    ]

    def get_platform(self):
        machine = self.game_config.get('machine')
        if machine:
            for index, machine_choice in enumerate(self.machine_choices):
                if machine_choice[1] == machine:
                    return self.platforms[index]
        return ''

    @property
    def working_dir(self):
        return os.path.join(os.path.expanduser("~"), ".mame")

    def play(self):
        rompath = self.runner_config.get('rompath') or ''
        if not system.path_exists(rompath):
            logger.warning("BIOS path provided in %s doesn't exist", rompath)
            rompath = os.path.join(settings.RUNNER_DIR, "mess/bios")
        if not system.path_exists(rompath):
            logger.error("Couldn't find %s", rompath)
            return {'error': 'NO_BIOS'}
        machine = self.game_config.get('machine')
        if not machine:
            return {'error': 'INCOMPLETE_CONFIG'}
        rom = self.game_config.get('main_file') or ''
        if rom and not system.path_exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        device = self.game_config.get('device')
        command = [self.get_executable()]
        if self.runner_config.get('uimodekey'):
            command += ['-uimodekey', self.runner['uimodekey']]

        command += ['-rompath', rompath, machine]
        if device:
            command.append('-' + device)
        if rom:
            command.append(rom)
        return {'command': command}
