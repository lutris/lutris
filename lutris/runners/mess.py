import os
from lutris import settings
from lutris.util.log import logger
from lutris.runners.runner import Runner


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
            'help': ("The game data, commonly called a ROM image.")
        },
        {
            'option': 'machine',
            'type': 'choice_with_entry',
            'label': "Machine",
            'choices': machine_choices,
            'help': ("The emulated machine.")
        },
        {
            'option': 'device',
            'type': 'choice_with_entry',
            'label': "Storage type",
            'choices': [
                ("Floppy disk", 'flop'),
                ("Floppy drive 1", 'flop1'),
                ("Floppy drive 2", 'flop2'),
                ("Cassette (tape)", 'cass'),
                ("Cartridge", 'cart'),
                ("Snapshot", 'snapshot'),
                ("Quickload", 'quickload'),
                ("CDROM", 'cdrm'),
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
        if not os.path.exists(rompath):
            logger.warning("BIOS path provided in %s doesn't exist", rompath)
            rompath = os.path.join(settings.RUNNER_DIR, "mess/bios")
        if not os.path.exists(rompath):
            logger.error("Couldn't find %s", rompath)
            return {'error': 'NO_BIOS'}
        machine = self.game_config.get('machine')
        if not machine:
            return {'error': 'INCOMPLETE_CONFIG'}
        rom = self.game_config.get('main_file') or ''
        if rom and not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        device = self.game_config.get('device')
        command = [self.get_executable(),
                   '-uimodekey', 'RCONTROL',
                   '-rompath', rompath, machine]
        if device:
            command.append('-' + device)
        if rom:
            command.append(rom)
        return {'command': command}
