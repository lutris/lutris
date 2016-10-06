import os
from lutris.runners.runner import Runner
from lutris import settings


def get_cores():
    return [
        ('4do (3DO)', '4do'),
        ('gambatte (Game Boy Color)', 'gambatte'),
        ('genesis plus gx (Sega Genesis)', 'genesis_plus_gx'),
        ('mupen64plus (Nintendo 64)', 'mupen64plus'),
        ('pcsx rearmed (Sony Playstation)', 'pcsx_rearmed'),
        ('mednafen psx (Sony Playstation)', 'mednafen_psx'),
        ('mednafen psx OpenGL (Sony Playstation)', 'mednafen_psx_hw'),
        ('reicast (Sega Dreamcast)', 'reicast'),
        ('snes9x (Super Nintendo)', 'snes9x'),
        ('yabause (Sega Saturn)', 'yabause'),
        ('vba next (Game Boy Advance)', 'vba_next'),
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

    def play(self):
        command = [self.get_executable()]

        # Fullscreen
        fullscreen = self.runner_config.get('fullscreen')
        if fullscreen:
            command.append('--fullscreen')

        # Core
        core = self.game_config['core']
        command.append('--libretro={}'.format(self.get_core_path(core)))

        # Main file
        file = self.game_config.get('main_file')
        if file:
            command.append(file)

        return {'command': command}
