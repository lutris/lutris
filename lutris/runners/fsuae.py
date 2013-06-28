import os

from lutris.runners.uae import uae
from lutris.gui.dialogs import ErrorDialog, DownloadDialog
from lutris.util.extract import extract_archive
from lutris import settings

RUNNER_DIR = os.path.join(settings.DATA_DIR, "runners")


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
                "option": "kickstart_file",
                "label": "Rom Path",
                "type": "file_chooser"
            }
        ]
        self.settings = settings

    def insert_floppies(self):
        disks = []
        main_disk = self.settings['game'].get('main_file')
        if main_disk:
            disks.append(main_disk)

        additional_disks = self.settings['game'].get('disks', [])
        disks += additional_disks
        floppy_params = []
        for drive, disk in enumerate(disks):
            floppy_params.append("--floppy_drive_%d=\"%s\"" % (drive, disk))
        return floppy_params

    def is_installed(self):
        if os.path.exists(self.get_executable()):
            return True
        return super(fsuae, self).is_installed()

    def install(self):
        """Downloads deb package and installs it"""
        runner_urls = {
            'i686': settings.RUNNERS_URL + "fs-uae-i386.tar.gz",
            'x64': settings.RUNNERS_URL + "fs-uae-x86_64.tar.gz",
            'x86_64': settings.RUNNERS_URL + "fs-uae-x86_64.tar.gz"
        }
        download_url = runner_urls.get(self.arch)
        if not download_url:
            ErrorDialog(
                "Runner not available for architecture %s" % self.arch
            )
        runner_filename = os.path.basename(download_url)
        dest = os.path.join(settings.CACHE_DIR, runner_filename)
        dialog = DownloadDialog(download_url, dest)
        dialog.run()
        extract_archive(dest, RUNNER_DIR)

    def get_executable(self):
        return os.path.join(RUNNER_DIR, 'fs-uae/bin/fs-uae')

    def get_params(self):
        runner = self.__class__.__name__
        params = []
        runner_config = self.settings[runner] or {}
        machine = runner_config.get('machine')
        kickstart_file = runner_config.get('kickstart_file')
        if kickstart_file:
            params.append("--kickstart_file=\"%s\"" % kickstart_file)
        if machine:
            params.append('--amiga_model=%s' % machine)
        if runner_config.get("gfx_fullscreen_amiga", False):
            params.append("--fullscreen")
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
