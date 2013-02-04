from lutris.runners.uae import uae


class fsuae(uae):
    """Run Amiga games with FS-UAE"""

    def __init__(self, settings=None):
        super(fsuae, self).__init__(settings)
        self.executable = 'fs-uae'
        self.homepage = 'http://fengestad.no/fs-uae'
        self.package = {
            'x86': self.homepage + '/stable/2.0.1/fs-uae_2.0.1-0_i386.deb',
            'x64': self.homepage + '/stable/2.0.1/fs-uae_2.0.1-0_amd64.deb'
        }

    def insert_floppies(self):
        floppies = self.settings['game'].get('disk', [])
        params = []
        for drive, disk in enumerate(floppies):
            params.append("--floppy_drive_%d=\"%s\"" % (drive, disk))
        return params

    def get_params(self):
        runner = self.__class__.__name__
        params = []
        if "machine" in self.settings[runner]:
            machine = self.settings[runner]['machine']
            params.append('--amiga_model=%s' % machine)
        if self.settings[runner].get("gfx_fullscreen_amiga", False):
            params.append("--fullscreen")
        return params
