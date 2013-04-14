import os
import subprocess

from lutris.runners.uae import uae
from lutris.gui.dialogs import ErrorDialog, DownloadDialog
from lutris.settings import CACHE_DIR


class fsuae(uae):
    """Run Amiga games with FS-UAE"""

    def __init__(self, settings=None):
        super(fsuae, self).__init__(settings)
        self.executable = 'fs-uae'
        self.homepage = 'http://fengestad.no/fs-uae'
        self.package = {
            'i686': self.homepage + '/stable/2.0.1/fs-uae_2.0.1-0_i386.deb',
            'x64': self.homepage + '/stable/2.0.1/fs-uae_2.0.1-0_amd64.deb'
        }
        self.settings = settings

    def insert_floppies(self):
        floppies = self.settings['game'].get('disk', [])
        if type(floppies) == str:
            floppies = [floppies]
        params = []
        for drive, disk in enumerate(floppies):
            params.append("--floppy_drive_%d=\"%s\"" % (drive, disk))
        return params

    def install(self):
        """Downloads deb package and installs it"""
        download_url = self.package.get(self.arch)
        if not download_url:
            ErrorDialog(
                "Runner not available on your architecture"
            )
        deb_filename = os.path.basename(download_url)
        dest = os.path.join(CACHE_DIR, deb_filename)
        dialog = DownloadDialog(download_url, dest)
        dialog.run()
        subprocess.Popen(["software-center", dest],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)

    def get_params(self):
        runner = self.__class__.__name__
        params = []
        runner_config = self.settings[runner] or {}
        machine = runner_config.get('machine')
        if machine:
            params.append('--amiga_model=%s' % machine)
        if runner_config.get("gfx_fullscreen_amiga", False):
            params.append("--fullscreen")
        return params
