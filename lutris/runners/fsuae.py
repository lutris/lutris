import os

from lutris import settings
from lutris.runners.uae import uae
from lutris.gui.dialogs import ErrorDialog
from lutris.util.display import get_current_resolution


class fsuae(uae):
    """Run Amiga games with FS-UAE"""

    def __init__(self, settings=None):
        super(fsuae, self).__init__(settings)
        self.executable = 'fs-uae'
        self.game_options = [
            {
                'option': "main_file",
                'type': "file",
                'label': "Boot disk"
            },
            {
                "option": "disks",
                "type": "multiple",
                "label": "Additionnal floppies"
            }
        ]

        self.runner_options = [
            {
                "option": "model",
                "label": "Amiga model",
                "type": "choice",
                "choices": [
                    ("Amiga 500 (default)", 'A500'),
                    ("Amiga 500+ with 1 MB chip RAM", 'A500+'),
                    ("Amiga 600 with 1 MB chip RAM", 'A600'),
                    ("Amiga 1000 with 512 KB chip RAM", 'A1000'),
                    ("Amiga 1200 with 2 MB chip RAM", 'A1200'),
                    ("Amiga 1200 but with 68020 processor", 'A1200/020'),
                    ("Amiga 4000 with 2 MB chip RAM and a 68040", 'A4000/040'),
                    ("CD32 unit", 'CD32'),
                    ("Commodore CDTV unit", 'CDTV'),
                ]
            },
            {
                "option": "kickstart_file",
                "label": "Rom Path",
                "type": "file"
            },
            {
                "option": "gfx_fullscreen_amiga",
                "label": "Fullscreen (F12 + s to Switch)",
                "type": "bool"
            },
            {
                "option": "scanlines",
                "label": "Enable scanlines",
                "type": "bool"
            }
        ]
        self.settings = settings

    def insert_floppies(self):
        disks = []
        main_disk = self.settings['game'].get('main_file')
        if main_disk:
            disks.append(main_disk)

        game_disks = self.settings['game'].get('disks', [])
        for disk in game_disks:
            if disk not in disks:
                disks.append(disk)
        runner_settings = self.settings.get('fsuae') or {}
        amiga_model = runner_settings.get('model')
        if amiga_model in ('CD32', 'CDTV'):
            disk_param = 'cdrom_drive'
        else:
            disk_param = 'floppy_drive'
        floppy_drives = []
        floppy_images = []
        for drive, disk in enumerate(disks):
            floppy_drives.append("--%s_%d=\"%s\"" % (disk_param, drive, disk))
            floppy_images.append("--floppy_image_%d=\"%s\"" % (drive, disk))
        return floppy_drives + floppy_images

    def is_installed(self):
        if os.path.exists(self.get_executable()):
            return True
        return super(fsuae, self).is_installed()

    def install(self):
        """Downloads deb package and installs it"""
        tarballs = {
            'i386': "fs-uae-i386.tar.gz",
            'x64': "fs-uae-x86_64.tar.gz",
        }
        tarball = tarballs.get(self.arch)
        if not tarball:
            ErrorDialog(
                "Runner not available for architecture %s" % self.arch
            )
        self.download_and_extract(tarball)

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'fs-uae/bin/fs-uae')

    def get_params(self):
        runner = self.__class__.__name__
        params = []
        runner_config = self.settings[runner] or {}
        model = runner_config.get('model')
        kickstart_file = runner_config.get('kickstart_file')
        if kickstart_file:
            params.append("--kickstart_file=\"%s\"" % kickstart_file)
        if model:
            params.append('--amiga_model=%s' % model)
        if runner_config.get("gfx_fullscreen_amiga", False):
            width = int(get_current_resolution().split('x')[0])
            params.append("--fullscreen")
            #params.append("--fullscreen_mode=fullscreen-window")
            params.append("--fullscreen_mode=fullscreen")
            params.append("--fullscreen_width=%d" % width)
        if runner_config.get('scanlines'):
            params.append("--scanlines=1")
        return params

    def play(self):
        params = self.get_params()
        disks = self.insert_floppies()
        command = [self.get_executable()]
        for param in params:
            command.append(param)
        for disk in disks:
            command.append(disk)
        return {'command': command}
