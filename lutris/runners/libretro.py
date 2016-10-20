import os
from lutris.runners.runner import Runner
from lutris import settings


def get_cores():
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
        ('O2EM (Magnavox Odyssey 2)', 'o2em'),
        ('PCSX Rearmed (Sony Playstation)', 'pcsx_rearmed'),
        ('PicoDrive (Sega Genesis)', 'picodrive'),
        ('PPSSPP (PlayStation Portable)', 'ppsspp'),
        ('Reicast (Sega Dreamcast)', 'reicast'),
        ('Snes9x (Super Nintendo)', 'snes9x'),
        ('Yabause (Sega Saturn)', 'yabause'),
        ('VBA Next (Game Boy Advance)', 'vba_next'),
        ('VBA-M (Game Boy Advance)', 'vbam'),
    ]


class libretro(Runner):
    human_name = "libretro"
    description = "Multi system emulator"
    platform = "libretro"
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
        }
    ]

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
            super(libretro, self).install(version, downloader, callback)

        if not self.is_retroarch_installed():
            super(libretro, self).install(version=None,
                                          downloader=downloader,
                                          callback=install_core)
        else:
            super(libretro, self).install(version, downloader, callback)

    def get_run_data(self):
        return {
            'command': [self.get_executable()] + self.get_runner_parameters()
        }

    def get_runner_parameters(self):
        parameters = []
        # Fullscreen
        fullscreen = self.runner_config.get('fullscreen')
        if fullscreen:
            parameters.append('--fullscreen')
        return parameters

    def play(self):
        command = [self.get_executable()]

        command += self.get_runnner_parameters()

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
