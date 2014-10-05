import os
import subprocess

from lutris import settings
from lutris.gui import dialogs
from lutris.util.log import logger
from lutris.util.system import find_executable
from lutris.runners.runner import Runner

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
DEFAULT_WINE = '1.7.13'


def set_regedit(path, key, value, wine_path=None, prefix=None):
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
    wineexec('regedit', args=reg_path, prefix=prefix, wine_path=wine_path)
    os.remove(reg_path)


def create_prefix(prefix, wine_path='wineboot', arch='win32'):
    """Create a new wineprefix"""
    wineexec('', prefix=prefix, wine_path=wine_path, arch=arch)


def wineexec(executable, args="", prefix=None, wine_path=None, arch=None,
             working_dir=None):
    executable = str(executable) if executable else ''
    prefix = 'WINEPREFIX="%s" ' % prefix if prefix else ''
    if arch not in ('win32', 'win64'):
        arch = detect_prefix_arch(prefix)
    if not wine_path:
        wine_path = wine().get_executable()
    if not working_dir:
        if os.path.isfile(executable):
            working_dir = os.path.dirname(executable)

    if 'winetricks' == wine_path:
        winetricks_env = 'WINE="%s"' % wine().get_executable()
    else:
        winetricks_env = ''

    if executable:
        executable = '"%s"' % executable

    command = '%s WINEARCH=%s %s "%s" %s %s' % (
        winetricks_env, arch, prefix, wine_path, executable, args
    )
    logger.debug("START wineexec(%s)", command)
    subprocess.Popen(command, cwd=working_dir, shell=True,
                     stdout=subprocess.PIPE).communicate()
    logger.debug("END wineexec")


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
        directory = os.path.expanduser("~/.wine")
    registry_path = os.path.join(directory, 'system.reg')
    if not os.path.isdir(directory) or not os.path.isfile(registry_path):
        # No directory exists or invalid prefix
        # returning 32 bit to create a new prefix.
        logger.debug("No prefix found in %s, defaulting to 32bit", directory)
        return 'win32'
    with open(registry_path, 'r') as registry:
        for i in range(5):
            line = registry.readline()
            if 'win64' in line:
                logger.debug("Detected 64bit prefix in %s", directory)
                return 'win64'
            elif 'win32' in line:
                logger.debug("Detected 32bit prefix in %s", directory)
                return 'win32'
    logger.debug("Can't detect prefix arch for %s, defaulting to 32bit",
                 directory)
    return 'win32'


def set_drive_path(prefix, letter, path):
    dosdevices_path = os.path.join(prefix, "dosdevices")
    if not os.path.exists(dosdevices_path):
        raise OSError("Invalid prefix path %s" % prefix)
    drive_path = os.path.join(dosdevices_path, letter + ":")
    logger.debug("Linking %s to %s", drive_path, path)
    os.symlink(drive_path, path)


# pylint: disable=C0103
class wine(Runner):
    """Run Windows games with Wine."""
    executable = 'wine'
    platform = 'Windows'
    game_options = [
        {
            'option': 'exe',
            'type': 'file',
            'label': 'Executable',
            'help': "The game's main EXE file"
        },
        {
            'option': 'args',
            'type': 'string',
            'label': 'Arguments',
            'help': ("Windows command line arguments used when launching "
                     "the game")
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": "Working directory",
            'help': ("The location where the game is run from.\n"
                     "By default, Lutris uses the directory of the "
                     "executable.")
        },

        {
            'option': 'prefix',
            'type': 'directory_chooser',
            'label': 'Prefix',
            'help': ("The prefix (also named \"bottle\") used by Wine.\n"
                     "It's a directory containing a set of files and "
                     "folders making up a confined Windows environment.")
        },
        {
            'option': 'arch',
            'type': 'choice',
            'label': 'Prefix architecture',
            'choices': [('Auto', 'auto'),
                        ('32-bit', 'win32'),
                        ('64-bit', 'win64')],
            'default': 'None',
            'help': ("The architecture of the Windows environment.\n"
                     "32-bit is recommended unless running "
                     "a 64-bit only game.")
        }
    ]

    def __init__(self, config=None):
        super(wine, self).__init__(config)
        self.wineprefix = None
        wine_versions = \
            [('System (%s)' % self.system_wine_version, 'system')] + \
            [('Custom (select executable below)', 'custom')] + \
            [(version, version) for version in self.local_wine_versions]

        orm_choices = [('FBO', 'fbo'),
                       ('BackBuffer', 'backbuffer')]
        rtlm_choices = [('Disabled', 'disabled'),
                        ('ReadTex', 'readtex'),
                        ('ReadDraw', 'readdraw')]
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
                'default': DEFAULT_WINE,
                'help': ("The version of Wine used to launch the game.\n"
                         "Using the last version is generally recommended, "
                         "but some games work better on older versions.")
            },
            {
                'option': 'custom_wine_path',
                'label': "Custom Wine executable",
                'type': 'file',
                'help': (
                    "The Wine executable to be used if you have selected "
                    "\"Custom\" as the Wine version."
                )
            },
            {
                'option': 'Desktop',
                'label': 'Windowed (virtual desktop)',
                'type': 'choice',
                'choices': desktop_choices,
                'help': ("Run the whole Windows desktop in a window.\n"
                         "Otherwise, run it fullscreen.\n"
                         "This corresponds to Wine's Virtual Desktop option.")
            },
            # {
            #     'option': 'cdrom_path',
            #     'label': 'CDRom mount point',
            #     'type': 'directory_chooser'
            # },
            {
                'option': 'MouseWarpOverride',
                'label': 'Mouse Warp Override',
                'type': 'choice',
                'choices': [
                    ('Enable', 'enable'),
                    ('Disable', 'disable'),
                    ('Force', 'force')
                ],
                'help': (
                    "Override the default mouse pointer warping behavior\n"
                    "<b>Enable</b>: (default) warp the pointer when the mouse"
                    " is exclusively acquired \n"
                    "<b>Disable</b>: never warp the mouse pointer \n"
                    "<b>Force</b>: always warp the pointer"
                )
            },
            {
                'option': 'Multisampling',
                'label': 'Multisampling',
                'type': 'choice',
                'choices': [
                    ('Enabled', 'enabled'),
                    ('Disabled', 'disabled')
                ],
                'help': ("Set to Disabled to prevent applications from "
                         "seeing Wine's multisampling support. "
                         "This is another Wine legacy option that will most "
                         "likely disappear at some point. There should be "
                         "no reason to set this.")
            },
            {
                'option': 'OffscreenRenderingMode',
                'label': 'Offscreen Rendering Mode',
                'type': 'choice',
                'choices': orm_choices,
                'help': ("Select the offscreen rendering implementation.\n"
                         "<b>FBO</b>: (default) Use framebuffer objects for offscreen"
                         " rendering \n"
                         "<b>Backbuffer</b>: Render offscreen render targets in the"
                         " backbuffer.\n")
            },
            {
                'option': 'RenderTargetLockMode',
                'label': 'Render Target Lock Mode',
                'type': 'choice',
                'choices': rtlm_choices,
                'help': (
                    "Select which mode is used for onscreen render targets:\n"
                    "<b>Disabled</b>: Disables render target locking \n"
                    "<b>ReadTex</b>: (default) Reads by glReadPixels, writes by"
                    " drawing a textured quad \n"
                    "<b>ReadDraw</b>: Uses glReadPixels for reading and writing"
                )
            },
            {
                'option': 'Audio',
                'label': 'Audio driver',
                'type': 'choice',
                'choices': audio_choices,
                'help': "Which audio backend to use."
            }
        ]
        self.config = config or {}
        self.settings = self.config  # DEPRECATED
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

    @property
    def prefix_path(self):
        return self.config['game'].get('prefix')

    @property
    def game_exe(self):
        """Return the game's executable's path."""
        exe = self.config['game'].get('exe')
        if exe:
            if os.path.isabs(exe):
                return exe
            return os.path.join(self.game_path, exe)

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        return self.working_dir  # exe path

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.config['game'].get('working_dir')
        if option:
            return option
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        else:
            return super(wine, self).working_dir

    @property
    def local_wine_versions(self):
        """Return the list of downloaded Wine versions."""
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
        """Return the version of Wine installed on the system."""
        try:
            version = subprocess.check_output(["wine", "--version"])
        except OSError:
            return "not installed"
        else:
            return version.strip('wine-\n')

    @property
    def wine_arch(self):
        arch = self.config['game'].get('arch') or 'auto'
        prefix = self.config['game'].get('prefix') or ''
        if arch not in ('win32', 'win64'):
            arch = detect_prefix_arch(prefix)
        return arch

    @property
    def wine_version(self):
        """Return the Wine version to use."""
        return self.runner_config.get('version') or DEFAULT_WINE

    def get_executable(self):
        """Return the path to the Wine executable."""
        path = WINE_DIR
        custom_path = self.runner_config.get('custom_wine_path', '')
        version = self.wine_version

        if version == 'system':
            if find_executable('wine'):
                return 'wine'
            # Fall back on bundled Wine
            version = DEFAULT_WINE
        elif version == 'custom':
            if os.path.exists(custom_path):
                return custom_path
            version = DEFAULT_WINE

        version += '-i386'
        return os.path.join(path, version, 'bin/wine')

    def install(self):
        if self.wine_version in ['custom', 'system']:
            # Fall back on default bundled version
            version = DEFAULT_WINE
        else:
            version = self.wine_version
        version += '-i386'
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
                    "Let's fall back on Wine " + DEFAULT_WINE +
                    " bundled with Lutris, alright?\n\n"
                    "(To get rid of this message, either install Wine \n"
                    "or change the Wine version in the game's configuration.)")
        elif self.wine_version == 'custom':
            if os.path.exists(custom_path):
                return True
            else:
                dialogs.ErrorDialog(
                    "Your custom Wine version can't be launched.\n"
                    "Let's fall back on Wine " + DEFAULT_WINE +
                    " bundled with Lutris, alright? \n\n"
                    "(To get rid of this message, fix your "
                    "Custom Wine path \n"
                    "or change the Wine version in the game's configuration.)")
        if os.path.exists(self.get_executable()):
            return True
        return False

    @classmethod
    def msi_exec(cls, msi_file, quiet=False, prefix=None):
        msi_args = "/i %s" % msi_file
        if quiet:
            msi_args += " /q"
        return wineexec("msiexec", args=msi_args, prefix=prefix)

    def check_regedit_keys(self, wine_config):
        """Reset regedit keys according to config."""
        prefix = self.config['game'].get('prefix') or ''
        for key in self.reg_keys.keys():
            if key in self.runner_config:
                set_regedit(self.reg_keys[key], key, self.runner_config[key],
                            self.get_executable(), prefix)

    def prepare_launch(self):
        self.check_regedit_keys(self.runner_config)

    def play(self):
        prefix = self.config['game'].get('prefix') or ''
        arch = self.wine_arch
        arguments = self.config['game'].get('args') or ''

        if not os.path.exists(self.game_exe):
            return {'error': 'FILE_NOT_FOUND', 'file': self.game_exe}

        command = ['WINEARCH=%s' % arch]
        if os.path.exists(prefix):
            command.append("WINEPREFIX=\"%s\" " % prefix)
            self.wineprefix = prefix

        self.prepare_launch()
        command.append(self.get_executable())
        command.append('"%s"' % self.game_exe)
        if arguments:
            for arg in arguments.split():
                command.append(arg)
        return {'command': command}

    def stop(self):
        """The kill command runs wineserver -k."""
        wine_path = self.get_executable()
        wine_root = os.path.dirname(wine_path)
        command = os.path.join(wine_root, "wineserver") + " -k"
        if self.wineprefix:
            command = "WINEPREFIX=%s %s" % (self.wineprefix, command)
        logger.debug("Killing all wine processes: %s" % command)
        os.popen(command, shell=True)
