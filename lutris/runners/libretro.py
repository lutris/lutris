import os
from lutris.runners.runner import Runner
from lutris.util.libretro import RetroConfig
from lutris.util import system
from lutris.util.log import logger
from lutris import settings

# List of supported libretro cores
# First element is the human readable name for the core with the platform's short name
# Second element is the core identifier
# Third element is the platform's long name
LIBRETRO_CORES = [
    ('4do (3DO)', '4do', '3DO'),
    ('atari800 (Atari 800/5200)', 'atari800', 'Atari 800/5200'),
    ('blueMSX (MSX/MSX2/MSX+)', 'bluemsx', 'MSX/MSX2/MSX+'),
    ('Caprice32 (Amstrad CPC)', 'cap32', 'Amstrad CPC'),
    ('ChaiLove', 'chailove', 'ChaiLove'),
    ('Citra (Nintendo 3DS)', 'citra', 'Nintendo 3DS'),
    ('Citra Canary (Nintendo 3DS)', 'citra_canary', 'Nintendo 3DS'),
    ('CrocoDS (Amstrad CPC)', 'crocods', 'Amstrad CPC'),
    ('DesmuME (Nintendo DS)', 'desmume', 'Nintendo DS'),
    ('Dolphin (Nintendo Wii/Gamecube)', 'dolphin', 'Nintendo Wii/Gamecube'),
    ('EightyOne (Sinclair ZX81)', '81', 'Sinclair ZX81'),
    ('FCEUmm (Nintendo Entertainment System)', 'fceumm', 'Nintendo NES'),
    ('fMSX (MSX/MSX2/MSX2+)', 'fmsx', 'MSX/MSX2/MSX2+'),
    ('Fuse (ZX Spectrum)', 'fuse', 'Sinclair ZX Spectrum'),
    ('Gambatte (Game Boy Color)', 'gambatte', 'Nintendo Game Boy Color'),
    ('Genesis Plus GX (Sega Genesis)', 'genesis_plus_gx', 'Sega Genesis'),
    ('Handy (Atari Lynx)', 'handy', 'Atari Lynx'),
    ('Hatari (Atari ST/STE/TT/Falcon)', 'hatari', 'Atari ST/STE/TT/Falcon'),
    ('higan accuracy(Super Nintendo)', 'higan_sfc', 'Nintendo SNES'),
    ('higan balanced(Super Nintendo)', 'higan_sfc_balanced', 'Nintendo SNES'),
    ('MAME (Arcade)', 'mame', 'Arcade'),
    ('Mednafen GBA (Game Boy Advance)', 'mednafen_gba', 'Nintendo Game Boy Advance'),
    ('Mednafen NGP (SNK Neo Geo Pocket)', 'mednafen_ngp', 'SNK Neo Geo Pocket'),
    ('Mednafen PCE FAST (TurboGrafx-16)', 'mednafen_pce_fast', 'NEC PC Engine (TurboGrafx-16)'),
    ('Mednafen PCFX (NEC PC-FX)', 'mednafen_pcfx', 'NEC PC-FX'),
    ('Mednafen Saturn (Sega Saturn)', 'mednafen_saturn', 'Sega Saturn'),
    ('Mednafen SGX (NEC PC Engine SuperGrafx)', 'mednafen_supergrafx', 'NEC PC Engine (SuperGrafx)'),
    ('Mednafen WSWAN (Bandai WonderSwan)', 'mednafen_wswan', 'Bandai WonderSwan'),
    ('Mednafen PSX (Sony Playstation)', 'mednafen_psx', 'Sony PlayStation'),
    ('Mednafen PSX OpenGL (Sony Playstation)', 'mednafen_psx_hw', 'Sony PlayStation'),
    ('Mesen (Nintendo Entertainment System)', 'mesen', 'Nintendo NES'),
    ('mGBA (Game Boy Advance)', 'mgba', 'Nintendo Game Boy Advance'),
    ('Mupen64Plus (Nintendo 64)', 'mupen64plus', 'Nintendo N64'),
    ('Nestopia (Nintendo Entertainment System)', 'nestopia', 'Nintendo NES'),
    ('Neko Project 2 (NEC PC-98)', 'nekop2', 'NEC PC-98'),
    ('Neko Project II kai (NEC PC-98)', 'np2kai', 'NEC PC-98'),
    ('O2EM (Magnavox Odyssey²)', 'o2em', 'Magnavox Odyssey²'),
    ('PCSX Rearmed (Sony Playstation)', 'pcsx_rearmed', 'Sony PlayStation'),
    ('PicoDrive (Sega Genesis)', 'picodrive', 'Sega Genesis'),
    ('Portable SHARP X68000 Emulator (SHARP X68000)', 'px68k', 'Sharp X68000'),
    ('PPSSPP (PlayStation Portable)', 'ppsspp', 'Sony PlayStation Portable'),
    ('ProSystem (Atari 7800)', 'prosystem', 'Atari 7800'),
    ('Redream (Sega Dreamcast)', 'redream', 'Sega Dreamcast'),
    ('Reicast (Sega Dreamcast)', 'reicast', 'Sega Dreamcast'),
    ('Snes9x (Super Nintendo)', 'snes9x', 'Nintendo SNES'),
    ('Stella (Atari 2600)', 'stella', 'Atari 2600'),
    ('VecX (Vectrex)', 'vecx', 'Vectrex'),
    ('Yabause (Sega Saturn)', 'yabause', 'Sega Saturn'),
    ('VBA Next (Game Boy Advance)', 'vba_next', 'Nintendo Game Boy Advance'),
    ('VBA-M (Game Boy Advance)', 'vbam', 'Nintendo Game Boy Advance'),
    ('Virtual Jaguar (Atari Jaguar)', 'virtualjaguar', 'Atari Jaguar'),
    ('VICE (Commodore 128)', 'vice_x128', 'Commodore 128'),
    ('VICE (Commodore 16/Plus/4)', 'vice_xplus4', 'Commodore 16/Plus/4'),
    ('VICE (Commodore 64)', 'vice_x64', 'Commodore 64'),
    ('VICE (Commodore VIC-20)', 'vice_xvic', 'Commodore VIC-20')
]


def get_core_choices():
    return [(core[0], core[1]) for core in LIBRETRO_CORES]


def get_default_config_path():
    return os.path.join(settings.RUNNER_DIR, 'retroarch/retroarch.cfg')


def get_default_assets_directory():
    return os.path.join(settings.RUNNER_DIR, 'retroarch/assets')


def get_default_cores_directory():
    return os.path.join(settings.RUNNER_DIR, 'retroarch/cores')


def get_default_info_directory():
    return os.path.join(settings.RUNNER_DIR, 'retroarch/info')


class libretro(Runner):
    human_name = "Libretro"
    description = "Multi system emulator"
    runnable_alone = True
    runner_executable = 'retroarch/retroarch'

    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
        },
        {
            'option': 'core',
            'type': 'choice',
            'label': 'Core',
            'choices': get_core_choices(),
        }
    ]

    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': True
        },
        {
            'option': 'config_file',
            'type': 'file',
            'label': 'Config file',
            'default': get_default_config_path()
        }
    ]

    @property
    def platforms(self):
        return [core[2] for core in LIBRETRO_CORES]

    def get_platform(self):
        game_core = self.game_config.get('core')
        if game_core:
            for core in LIBRETRO_CORES:
                if core[1] == game_core:
                    return core[2]
        return ''

    def get_core_path(self, core):
        return os.path.join(settings.RUNNER_DIR,
                            'retroarch/cores/{}_libretro.so'.format(core))

    def get_version(self, use_default=True):
        return self.game_config['core']

    def is_retroarch_installed(self):
        return os.path.exists(self.get_executable())

    def is_installed(self, core=None):
        if self.game_config.get('core') and core is None:
            core = self.game_config['core']
        if not core or self.runner_config.get('runner_executable'):
            return self.is_retroarch_installed()
        is_core_installed = os.path.exists(self.get_core_path(core))
        return self.is_retroarch_installed() and is_core_installed

    def install(self, version=None, downloader=None, callback=None):
        def install_core():
            if not version:
                if callback:
                    callback()
            else:
                super(libretro, self).install(version, downloader, callback)

        if not self.is_retroarch_installed():
            super(libretro, self).install(version=None,
                                          downloader=downloader,
                                          callback=install_core)
        else:
            super(libretro, self).install(version, downloader, callback)

    def get_run_data(self):
        self.prelaunch()
        return {
            'command': [self.get_executable()] + self.get_runner_parameters()
        }

    def get_config_file(self):
        return self.runner_config.get('config_file') or get_default_config_path()

    def get_system_directory(self, retro_config):
        """Return the system directory used for storing BIOS and firmwares."""
        system_directory = retro_config['system_directory']
        if not system_directory or system_directory == 'default':
            system_directory = '~/.config/retroarch/system'
        return os.path.expanduser(system_directory)

    def prelaunch(self):
        config_file = self.get_config_file()
        if not os.path.exists(config_file):
            logger.warning("Unable to find retroarch config. Except erratic behavior")
            return True
        retro_config = RetroConfig(config_file)

        retro_config['libretro_directory'] = get_default_cores_directory()
        retro_config['libretro_info_path'] = get_default_info_directory()

        # Change assets path to the Lutris provided one if necessary
        assets_directory = os.path.expanduser(retro_config['assets_directory'])
        if system.path_is_empty(assets_directory):
            retro_config['assets_directory'] = get_default_assets_directory()
        retro_config.save()

        core = self.game_config.get('core')
        info_file = os.path.join(get_default_info_directory(),
                                 '{}_libretro.info'.format(core))
        if os.path.exists(info_file):
            core_config = RetroConfig(info_file)
            try:
                firmware_count = int(core_config['firmware_count'])
            except (ValueError, TypeError):
                firmware_count = 0
            system_path = self.get_system_directory(retro_config)
            notes = core_config['notes'] or ''
            checksums = {}
            if notes.startswith('Suggested md5sums:'):
                parts = notes.split('|')
                for part in parts[1:]:
                    checksum, filename = part.split(' = ')
                    checksums[filename] = checksum
            for index in range(firmware_count):
                firmware_filename = core_config['firmware%d_path' % index]
                firmware_path = os.path.join(system_path, firmware_filename)
                if os.path.exists(firmware_path):
                    if firmware_filename in checksums:
                        checksum = system.get_md5_hash(firmware_path)
                        if checksum == checksums[firmware_filename]:
                            checksum_status = 'Checksum good'
                        else:
                            checksum_status = 'Checksum failed'
                    else:
                        checksum_status = 'No checksum info'
                    logger.info("Firmware '{}' found ({})".format(firmware_filename,
                                                                  checksum_status))
                else:
                    logger.warning("Firmware '{}' not found!".format(firmware_filename))

                # Before closing issue #431
                # TODO check for firmware*_opt and display an error message if
                # firmware is missing
                # TODO Add dialog for copying the firmware in the correct
                # location

        return True

    def get_runner_parameters(self):
        parameters = []
        # Fullscreen
        fullscreen = self.runner_config.get('fullscreen')
        if fullscreen:
            parameters.append('--fullscreen')

        parameters.append('--config={}'.format(self.get_config_file()))
        return parameters

    def play(self):
        command = [self.get_executable()]

        command += self.get_runner_parameters()

        # Core
        core = self.game_config.get('core')
        if not core:
            return {
                'error': 'CUSTOM',
                'text': "No core has been selected for this game"
            }
        command.append('--libretro={}'.format(self.get_core_path(core)))

        # Main file
        file = self.game_config.get('main_file')
        if not file:
            return {
                'error': 'CUSTOM',
                'text': 'No game file specified'
            }
        if not os.path.exists(file):
            return {
                'error': 'FILE_NOT_FOUND',
                'file': file
            }
        command.append(file)
        return {'command': command}
