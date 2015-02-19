import os
import subprocess

from textwrap import dedent

from lutris import settings
from lutris.gui import dialogs
from lutris.util.log import logger
from lutris.util import system
from lutris.runners.runner import Runner

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
DEFAULT_WINE = '1.7.29'


def set_regedit(path, key, value='', type_='REG_SZ',
                wine_path=None, prefix=None):
    """Add keys to the windows registry

    Path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
    """
    logger.debug("Setting wine registry key : %s\\%s to %s",
                 path, key, value)
    reg_path = os.path.join(settings.CACHE_DIR, 'winekeys.reg')
    formatted_value = {
        'REG_SZ': '"%s"' % value,
        'REG_DWORD': 'dword:' + value,
        'REG_BINARY': 'hex:' + value.replace(' ', ','),
        'REG_MULTI_SZ': 'hex(2):' + value,
        'REG_EXPAND_SZ': 'hex(7):' + value,
    }
    # Make temporary reg file
    reg_file = open(reg_path, "w")
    reg_file.write(dedent(
        """
        REGEDIT4
        [%s]
        "%s"=%s
        """ % (path, key, formatted_value[type_])))
    reg_file.close()
    set_regedit_file(reg_path, wine_path=wine_path, prefix=prefix)
    os.remove(reg_path)


def set_regedit_file(filename, wine_path=None, prefix=None):
    """Apply a regedit file to the Windows registry"""
    wineexec('regedit', args=filename, wine_path=wine_path, prefix=prefix)


def create_prefix(prefix, wine_dir=None, arch='win32'):
    """Create a new wineprefix"""
    logger.debug("Creating a Wine prefix in %s", prefix)
    if not wine_dir:
        wine_dir = os.path.dirname(wine().get_executable())
    wineboot_path = os.path.join(wine_dir, 'wineboot')

    env = ['WINEARCH=%s' % arch]
    if prefix:
        env.append('WINEPREFIX="%s" ' % prefix)

    command = " ".join(env) + wineboot_path
    subprocess.Popen(command, cwd=None, shell=True,
                     stdout=subprocess.PIPE).communicate()
    if prefix:
        disable_desktop_integration(prefix)


def wineexec(executable, args="", wine_path=None, prefix=None, arch=None,
             working_dir=None, winetricks_env=''):
    detected_arch = detect_prefix_arch(prefix)
    executable = str(executable) if executable else ''
    if arch not in ('win32', 'win64'):
        arch = detected_arch or 'win32'
    if not wine_path:
        wine_path = wine().get_executable()
    if not working_dir:
        if os.path.isfile(executable):
            working_dir = os.path.dirname(executable)

    if executable.endswith(".msi"):
        executable = 'msiexec /i "%s"' % executable
    elif executable:
        executable = '"%s"' % executable

    # Create prefix if necessary
    if not detected_arch:
        create_prefix(prefix, wine_dir=os.path.dirname(wine_path), arch=arch)

    env = ['WINEARCH=%s' % arch]
    if winetricks_env:
        env.append('WINE="%s"' % winetricks_env)
    if prefix:
        env.append('WINEPREFIX="%s" ' % prefix)

    if settings.RUNNER_DIR in wine_path:
        runtime32_path = os.path.join(settings.RUNTIME_DIR, "lib32")
        env.append('LD_LIBRARY_PATH={}'.format(runtime32_path))

    command = '{0} "{1}" {2} {3}'.format(
        " ".join(env), wine_path, executable, args
    )
    subprocess.Popen(command, cwd=working_dir, shell=True,
                     stdout=subprocess.PIPE).communicate()


def winetricks(app, prefix=None, winetricks_env=None, silent=False):
    arch = detect_prefix_arch(prefix) or 'win32'
    if not winetricks_env:
        winetricks_env = wine().get_executable()
    if str(silent).lower() in ('yes', 'on', 'true'):
        args = "-q " + app
    else:
        args = app
    wineexec(None, prefix=prefix, winetricks_env=winetricks_env,
             wine_path='winetricks', arch=arch, args=args)


def detect_prefix_arch(directory=None):
    """Return the architecture of the prefix found in `directory`.

    If no `directory` given, return the arch of the system's default prefix.
    If no prefix found, return None."""
    if not directory:
        directory = os.path.expanduser("~/.wine")
    registry_path = os.path.join(directory, 'system.reg')
    if not os.path.isdir(directory) or not os.path.isfile(registry_path):
        # No directory exists or invalid prefix
        logger.debug("No prefix found in %s", directory)
        return
    with open(registry_path, 'r') as registry:
        for i in range(5):
            line = registry.readline()
            if 'win64' in line:
                logger.debug("Detected 64bit prefix in %s", directory)
                return 'win64'
            elif 'win32' in line:
                logger.debug("Detected 32bit prefix in %s", directory)
                return 'win32'
    logger.debug("Can't detect prefix arch for %s", directory)


def disable_desktop_integration(prefix):
    """Remove links to user directories in a prefix."""
    if not prefix:
        raise ValueError('Missing prefix')
    user = os.getenv('USER')
    user_dir = os.path.join(prefix, "drive_c/users/", user)
    # Replace symlinks
    if os.path.exists(user_dir):
        for item in os.listdir(user_dir):
            path = os.path.join(user_dir, item)
            if os.path.islink(path):
                os.unlink(path)
                os.makedirs(path)


def set_drive_path(prefix, letter, path):
    dosdevices_path = os.path.join(prefix, "dosdevices")
    if not os.path.exists(dosdevices_path):
        raise OSError("Invalid prefix path %s" % prefix)
    drive_path = os.path.join(dosdevices_path, letter + ":")
    if os.path.exists(drive_path):
        os.remove(drive_path)
    logger.debug("Linking %s to %s", drive_path, path)
    os.symlink(path, drive_path)


def get_wine_versions():
    """Return the list of Wine versions installed by lutris.

    :returns: list of (version, architecture) tuples
    """
    if not os.path.exists(WINE_DIR):
        return []
    dirs = os.listdir(WINE_DIR)
    versions = []
    for dirname in dirs:
        split = dirname.split('-')
        if len(split) == 2 and is_version_installed(split[0], split[1]):
            versions.append((split[0], split[1]))
    return versions


def get_wine_exes():
    """Return the list of wine executables installed"""
    versions = []
    for version, arch in get_wine_versions():
        versions.append(get_wine_version_exe(version, arch))
    return versions


def get_wine_version_exe(version, arch=None):
    arch = arch if arch else 'i386'
    return os.path.join(WINE_DIR, '%s-%s/bin/wine' % (version, arch))


def is_version_installed(version, arch=None):
    arch = arch if arch else 'i386'
    return os.path.isfile(get_wine_version_exe(version, arch))


# pylint: disable=C0103
class wine(Runner):
    """Run Windows games with Wine."""
    human_name = "Wine"
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
            'default': 'auto',
            'help': ("The architecture of the Windows environment.\n"
                     "32-bit is recommended unless running "
                     "a 64-bit only game.")
        }
    ]

    def __init__(self, config=None):
        super(wine, self).__init__(config)
        wine_versions = \
            [('System (%s)' % self.system_wine_version, 'system')] + \
            [('Custom (select executable below)', 'custom')] + \
            [(version, version) for version, arch in get_wine_versions()]

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
                         "<b>FBO</b>: (default) Use framebuffer objects for "
                         "offscreen rendering \n"
                         "<b>Backbuffer</b>: Render offscreen render targets "
                         "in the backbuffer.\n")
            },
            {
                'option': 'RenderTargetLockMode',
                'label': 'Render Target Lock Mode',
                'type': 'choice',
                'choices': rtlm_choices,
                'help': (
                    "Select which mode is used for onscreen render targets:\n"
                    "<b>Disabled</b>: Disables render target locking \n"
                    "<b>ReadTex</b>: (default) Reads by glReadPixels, writes "
                    "by drawing a textured quad \n"
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
        return self.game_config.get('prefix')

    @property
    def game_exe(self):
        """Return the game's executable's path."""
        exe = self.game_config.get('exe') or ''
        if exe and os.path.isabs(exe):
            return exe
        return os.path.join(self.game_path, exe)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get('working_dir')
        if option:
            return option
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        else:
            return super(wine, self).working_dir

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
        """Return the wine architecture

        Get it from the config or detect it from the prefix"""
        arch = self.game_config.get('arch') or 'auto'
        if arch not in ('win32', 'win64'):
            arch = detect_prefix_arch(self.prefix_path) or 'win32'
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
            if system.find_executable('wine'):
                return 'wine'
            # Fall back on bundled Wine
            version = DEFAULT_WINE
        elif version == 'custom':
            if os.path.exists(custom_path):
                return custom_path
            version = DEFAULT_WINE

        version += '-i386'
        return os.path.join(path, version, 'bin/wine')

    def install(self, version=None, arch=None):
        if not version:
            version = self.wine_version
            if version in ['custom', 'system']:
                # Fall back on default bundled version
                version = DEFAULT_WINE
        arch = arch if arch else 'i386'
        tarball = "wine-%s-%s.tar.gz" % (version, arch)
        destination = os.path.join(WINE_DIR, '%s-%s' % (version, arch))
        self.download_and_extract(tarball, destination, merge_single=True)

    def is_installed(self):
        if self.wine_version == 'system':
            if system.find_executable('wine'):
                return True
            else:
                dialogs.ErrorDialog(
                    "Wine is not installed on your system.\n"
                    "Let's fall back on Wine " + DEFAULT_WINE +
                    " bundled with Lutris, alright?\n\n"
                    "(To get rid of this message, either install Wine \n"
                    "or change the Wine version in the game's configuration.)")
        elif self.wine_version == 'custom':
            custom_path = self.runner_config.get('custom_wine_path', '')
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
        return os.path.exists(self.get_executable())

    @classmethod
    def msi_exec(cls, msi_file, quiet=False, prefix=None):
        msi_args = "/i %s" % msi_file
        if quiet:
            msi_args += " /q"
        return wineexec("msiexec", args=msi_args, prefix=prefix)

    def check_regedit_keys(self, wine_config):
        """Reset regedit keys according to config."""
        prefix = self.prefix_path
        for key in self.reg_keys.keys():
            if key in self.runner_config:
                set_regedit(self.reg_keys[key], key,
                            value=self.runner_config[key],
                            wine_path=self.get_executable(), prefix=prefix)

    def prepare_launch(self):
        self.check_regedit_keys(self.runner_config)

    def get_env(self, full=True):
        if full:
            env = os.environ.copy()
        else:
            env = {}
        env['WINEDEBUG'] = "-fixme-all"
        env['WINEARCH'] = self.wine_arch
        if self.prefix_path:
            env['WINEPREFIX'] = self.prefix_path
        return env

    def play(self):
        game_exe = self.game_exe
        arguments = self.game_config.get('args') or ''

        if not os.path.exists(game_exe):
            return {'error': 'FILE_NOT_FOUND', 'file': game_exe}
        if game_exe.endswith(".msi"):
            game_exe = 'msiexec /i "%s"' % game_exe
        else:
            game_exe = '"%s"' % game_exe

        self.prepare_launch()
        env = self.get_env()
        command = [self.get_executable(), game_exe]
        if arguments:
            for arg in arguments.split():
                command.append(arg)
        return {'command': command, 'env': env}

    def stop(self):
        """The kill command runs wineserver -k."""
        wine_path = self.get_executable()
        wine_root = os.path.dirname(wine_path)
        env = self.get_env(full=True)
        command = os.path.join(wine_root, "wineserver") + " -k"
        logger.debug("Killing all wine processes: %s" % command)
        subprocess.Popen(command, env=env)

    @staticmethod
    def parse_wine_path(path, prefix_path=None):
        """Take a Windows path, return the corresponding Linux path."""
        path = path.replace("\\\\", "/").replace('\\', '/')
        if path.startswith('C'):
            if not prefix_path:
                prefix_path = os.path.expanduser("~/.wine")
            path = os.path.join(prefix_path, 'drive_c', path[3:])
        elif path[1] == ':':
            # Trim Windows path
            path = path[2:]
        return path
