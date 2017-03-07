import os
from lutris.runners.runner import Runner
from lutris.util.libretro import RetroConfig
from lutris.util import system
from lutris.util.log import logger
from lutris import settings


def get_cores():
    # Don't forget to update self.platforms
    # The order has to be the same!
    return [
        ('4do (3DO)', '4do'),
        ('FCEUmm (Nintendo Entertainment System)', 'fceumm'),
        ('Fuse (ZX Spectrum)', 'fuse'),
        ('Gambatte (Game Boy Color)', 'gambatte'),
        ('Genesis Plus GX (Sega Genesis)', 'genesis_plus_gx'),
        ('Handy (Atari Lynx)', 'handy'),
        ('Hatari (Atari ST/STE/TT/Falcon)', 'hatari'),
        ('Mednafen NGP (SNK Neo Geo Pocket)', 'mednafen_ngp'),
        ('Mednafen PCE FAST (TurboGrafx-16)', 'mednafen_pce_fast'),
        ('Mednafen PCFX (NEC PC-FX)', 'mednafen_pcfx'),
        ('Mednafen SGX (NEC PC Engine SuperGrafx)', 'mednafen_supergrafx'),
        ('Mednafen WSWAN (Bandai WonderSwan)', 'mednafen_wswan'),
        ('Mednafen PSX (Sony Playstation)', 'mednafen_psx'),
        ('Mednafen PSX OpenGL (Sony Playstation)', 'mednafen_psx_hw'),
        ('Mupen64Plus (Nintendo 64)', 'mupen64plus'),
        ('O2EM (Magnavox Odyssey²)', 'o2em'),
        ('PCSX Rearmed (Sony Playstation)', 'pcsx_rearmed'),
        ('PicoDrive (Sega Genesis)', 'picodrive'),
        ('PPSSPP (PlayStation Portable)', 'ppsspp'),
        ('Reicast (Sega Dreamcast)', 'reicast'),
        ('Snes9x (Super Nintendo)', 'snes9x'),
        ('Yabause (Sega Saturn)', 'yabause'),
        ('VBA Next (Game Boy Advance)', 'vba_next'),
        ('VBA-M (Game Boy Advance)', 'vbam'),
    ]


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
    platforms = (
        ('3DO',),
        ('Nintendo', 'NES'),
        ('Sinclair', 'ZX Spectrum'),
        ('Nintendo', 'Game Boy Color'),
        ('Sega', 'Genesis'),
        ('Atari', 'Lynx'),
        ('Atari', 'ST/STE/TT/Falcon'),
        ('SNK', 'Neo Geo Pocket'),
        ('NEC', 'PC Engine (TurboGrafx-16)'),
        ('NEC', 'PC-FX'),
        ('NEC', 'PC Engine (SuperGrafx)'),
        ('Bandai', 'WonderSwan'),
        ('Sony', 'PlayStation'),
        ('Sony', 'PlayStation'),
        ('Nintendo', 'N64'),
        ('Magnavox', 'Odyssey²'),
        ('Sony', 'PlayStation'),
        ('Sega', 'Genesis'),
        ('Sony', 'PlayStation Portable'),
        ('Sega', 'Dreamcast'),
        ('Nintendo', 'SNES'),
        ('Sega', 'Saturn'),
        ('Nintendo', 'Game Boy Advance'),
        ('Nintendo', 'Game Boy Advance'),
    )
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
            'choices': get_cores(),
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
    def platform(self):
        core = self.game_config.get('core')
        if core:
            cores = get_cores()
            for i, c in enumerate(cores):
                if c[1] == core:
                    return self.platforms[i]
        return ('',)

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
