import os
import subprocess

from lutris import settings
from lutris.gui import dialogs
from lutris.util.log import logger
from lutris.util.system import find_executable
from lutris.runners.runner import Runner

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
WINE_VERSION = '1.7.13'


def set_regedit(path, key, value, prefix=None):
    """ Plays with the windows registry
        path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
    """
    logger.debug("Setting wine registry key : %s\\%s to %s",
                 path, key, value)
    reg_path = os.path.join(settings.CACHE_DIR, 'winekeys.reg')
    # Make temporary reg file
    reg_file = open(reg_path, "w")
    reg_file.write("""REGEDIT4

[%s]
"%s"="%s"

""" % (path, key, value))
    reg_file.close()
    wineexec('regedit', args=reg_path, prefix=prefix)
    os.remove(reg_path)


def create_prefix(prefix, arch='win32'):
    """Create a new wineprefix"""
    wineexec('', prefix=prefix, wine_path='wineboot', arch=arch)


def wineexec(executable, args="", prefix=None, wine_path='wine', arch=None,
             workdir=None):
    if not arch:
        arch = detect_prefix_arch(prefix)
    if not prefix:
        prefix = ""
    else:
        prefix = "WINEPREFIX=\"%s\" " % prefix
    executable = str(executable) if executable else ""
    if " " in executable:
        executable = "\"%s\"" % executable
    if arch not in ('win32', 'win64'):
        raise ValueError("Invalid WINEARCH %s" % arch)
    command = "WINEARCH=%s %s %s %s %s" % (
        arch, prefix, wine_path, executable, args
    )
    logger.debug("Running wine command: %s", command)
    subprocess.Popen(command, cwd=workdir, shell=True,
                     stdout=subprocess.PIPE).communicate()


def winetricks(app, prefix=None, silent=False):
    arch = detect_prefix_arch(prefix)
    if str(silent).lower() in ('yes', 'on', 'true'):
        args = "-q " + app
    else:
        args = app
    wineexec(None, prefix=prefix, wine_path='winetricks', arch=arch, args=args)


def detect_prefix_arch(directory=None):
    """Given a wineprefix directory, return its architecture"""
    if not directory:
        directory = os.path.join(os.path.expanduser("~"), '.wine')
    registry_path = os.path.join(directory, 'system.reg')
    if not os.path.isdir(directory) or not os.path.isfile(registry_path):
        # No directory exists or invalid prefix
        # returning 32 bit to create a new prefix.
        return 'win32'
    with open(registry_path, 'r') as registry:
        for i in range(5):
            line = registry.readline()
            if 'win64' in line:
                return 'win64'
            elif 'win32' in line:
                return 'win32'
    return 'win32'


# pylint: disable=C0103
class wine(Runner):
    '''Run Windows games with Wine'''
    executable = 'wine'
    platform = 'Windows'
    game_options = [
        {
            'option': 'exe',
            'type': 'file',
            'label': 'Executable'
        },
        {
            'option': 'args',
            'type': 'string',
            'label': 'Arguments'
        },
        {
            'option': 'prefix',
            'type': 'directory_chooser',
            'label': 'Prefix'
        },
        {
            'option': 'arch',
            'type': 'choice',
            'label': 'Prefix architecture',
            'choices': [('32 bit', 'win32'),
                        ('64 bit', 'win64')],
            'default': 'win32'
        }
    ]

    def __init__(self, settings=None):
        super(wine, self).__init__()
        self.wineprefix = None
        wine_versions = \
            [('System (%s)' % self.system_wine_version, 'system')] + \
            [('Custom (select executable below)', 'custom')] + \
            [(version, version) for version in self.local_wine_versions]

        orm_choices = [('BackBuffer', 'backbuffer'),
                       ('FBO', 'fbo'),
                       ('PBuffer', 'pbuffer')]
        rtlm_choices = [('Auto', 'auto'),
                        ('Disabled', 'disabled'),
                        ('ReadDraw', 'readdraw'),
                        ('ReadTex', 'readtex'),
                        ('TexDraw', 'texdraw'),
                        ('TexTex', 'textex')]
        audio_choices = [('Alsa', 'alsa'),
                         ('OSS', 'oss'),
                         ('Jack', 'jack')]
        desktop_choices = [('Yes', 'Default'),
                           ('No', 'None')]
        self.runner_options = [
            {
                'option': 'version',
                'label': "Wine version",
                'type': 'choice',
                'choices': wine_versions,
                'default': WINE_VERSION
            },
            {
                'option': 'custom_wine_path',
                'label': "Custom Wine executable",
                'type': 'file'
            },
            {
                'option': 'cdrom_path',
                'label': 'CDRom mount point',
                'type': 'directory_chooser'
            },
            {
                'option': 'MouseWarpOverride',
                'label': 'Mouse Warp Override',
                'type': 'choice',
                'choices': [
                    ('Disable', 'disable'),
                    ('Enable', 'enable'),
                    ('Force', 'force')
                ]
            },
            {
                'option': 'Multisampling',
                'label': 'Multisampling',
                'type': 'choice',
                'choices': [
                    ('Enabled', 'enabled'),
                    ('Disabled', 'disabled')
                ]
            },
            {
                'option': 'OffscreenRenderingMode',
                'label': 'Offscreen Rendering Mode',
                'type': 'choice',
                'choices': orm_choices
            },
            {
                'option': 'RenderTargetLockMode',
                'label': 'Render Target Lock Mode',
                'type': 'choice',
                'choices': rtlm_choices
            },
            {
                'option': 'Audio',
                'label': 'Audio driver',
                'type': 'choice',
                'choices': audio_choices
            },
            {
                'option': 'Desktop',
                'label': 'Virtual desktop',
                'type': 'choice',
                'choices': desktop_choices
            }
        ]
        self.settings = settings or {}
        reg_prefix = "HKEY_CURRENT_USER\Software\Wine"
        self.reg_keys = {
            "RenderTargetLockMode": r"%s\Direct3D" % reg_prefix,
            "Audio": r"%s\Drivers" % reg_prefix,
            "MouseWarpOverride": r"%s\DirectInput" % reg_prefix,
            "Multisampling": r"%s\Direct3D" % reg_prefix,
            "OffscreenRenderingMode": r"%s\Direct3D" % reg_prefix,
            "DirectDrawRenderer": r"%s\Direct3D" % reg_prefix,
            "Version": r"%s" % reg_prefix,
            "Desktop": r"%s\Explorer" % reg_prefix
        }

    def get_game_path(self):
        """Return the path to browse with Browse Files from the context menu"""
        prefix = self.settings['game'].get('prefix')
        if prefix:
            return prefix
        game_exe = self.settings['game'].get('exe')
        if game_exe:
            exe_path = os.path.dirname(game_exe)
            if os.path.isabs(exe_path):
                return exe_path

    @property
    def local_wine_versions(self):
        """ Return the list of downloaded Wine versions """
        runner_path = WINE_DIR
        versions = []
        # Get list from folder names
        if os.path.exists(runner_path):
            dirnames = os.listdir(runner_path)
            # Make sure the Wine executable is present
            for version in dirnames:
                wine_exe = os.path.join(runner_path, version, 'bin/wine')
                if os.path.isfile(wine_exe):
                    version = version.replace('-i386', '')
                    versions.append(version)
        return versions

    @property
    def system_wine_version(self):
        """Return the version of Wine installed on the system"""
        try:
            version = subprocess.check_output(["wine", "--version"])
        except OSError:
            return "not installed"
        else:
            return version.strip('wine-\n')

    @property
    def wine_arch(self):
        game_config = self.settings.get('game', {})
        return game_config.get('arch', 'win32')

    @property
    def wine_version(self):
        """Return the Wine version to use"""
        return self.runner_config.get('version', WINE_VERSION)

    def get_executable(self):
        """Return the path to the Wine executable"""
        path = WINE_DIR
        custom_path = self.runner_config.get('custom_wine_path', '')
        version = self.wine_version

        if version == 'system':
            if find_executable('wine'):
                return 'wine'
            # Fall back on bundled Wine
            version = WINE_VERSION
        elif version == 'custom':
            if os.path.exists(custom_path):
                return custom_path
            version = WINE_VERSION

        version += '-i386'
        return os.path.join(path, version, 'bin/wine')

    def install(self):
        version = WINE_VERSION + '-i386'
        tarball = "wine-%s.tar.gz" % version
        destination = os.path.join(WINE_DIR, version)
        self.download_and_extract(tarball, destination, merge_single=True)

    def is_installed(self):
        custom_path = self.runner_config.get('custom_wine_path', '')
        if self.wine_version == 'system':
            if find_executable('wine'):
                return True
            else:
                dialogs.ErrorDialog(
                    "Wine is not installed on your system.\n"
                    "Let's fall back on Wine " + WINE_VERSION +
                    " bundled with Lutris, alright?\n\n"
                    "(To get rid of this message, either install Wine \n"
                    "or change the Wine version in the game's configuration.)")
        elif self.wine_version == 'custom':
            if os.path.exists(custom_path):
                return True
            else:
                dialogs.ErrorDialog(
                    "Your custom Wine version can't be launched.\n"
                    "Let's fall back on Wine " + WINE_VERSION +
                    " bundled with Lutris, alright? \n\n"
                    "(To get rid of this message, fix your "
                    "Custom Wine path \n"
                    "or change the Wine version in the game's configuration.)")
        if os.path.exists(self.get_executable()):
            return True
        return False

    @classmethod
    def msi_exec(cls, msi_file, quiet=False, prefix=None):
        msi_args = ["msiexec", "/i", msi_file]
        if quiet:
            msi_args.append("/q")
        return wineexec(msi_args, prefix=prefix)

    def check_regedit_keys(self, wine_config):
        """Resets regedit keys according to config"""
        for key in self.reg_keys.keys():
            if key in self.runner_config:
                set_regedit(self.reg_keys[key], key, self.runner_config[key])

    def prepare_launch(self):
        self.check_regedit_keys(self.runner_config)

    def play(self):
        command = ['WINEARCH=%s' % self.wine_arch]
        game_exe = self.settings['game'].get('exe')

        prefix = self.settings['game'].get('prefix', "")
        if os.path.exists(prefix):
            command.append("WINEPREFIX=\"%s\" " % prefix)
            self.wineprefix = prefix

        self.game_path = self.settings['game'].get('path')
        if not self.game_path:
            self.game_path = os.path.dirname(game_exe)
            game_exe = os.path.basename(game_exe)
        if not os.path.exists(self.game_path):
            if prefix:
                self.game_path = os.path.join(prefix, self.game_path)
            if not os.path.exists(self.game_path):
                return {"error": "FILE_NOT_FOUND", "file": self.game_path}

        arguments = self.settings['game'].get('args', "")
        self.prepare_launch()

        command.append(self.get_executable())
        command.append("\"%s\"" % game_exe)
        if arguments:
            for arg in arguments.split():
                command.append(arg)
        return {'command': command}

    def stop(self):
        """The kill command runs wineserver -k"""
        wine_path = self.get_executable()
        wine_root = os.path.dirname(wine_path)
        command = os.path.join(wine_root, wine_root, "wineserver") + " -k"
        if self.wineprefix:
            command = "WINEPREFIX=%s %s" % (self.wineprefix, command)
        logger.debug("Killing all wine processes: %s" % command)
        os.popen(command, shell=True)
