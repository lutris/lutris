import os
import shlex
import subprocess

from textwrap import dedent

from lutris import runtime
from lutris import settings
from lutris.util import datapath, display, system
from lutris.util.log import logger
from lutris.util.strings import version_sort
from lutris.runners.runner import Runner
from lutris.thread import LutrisThread

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
WINE_PATHS = {
    'winehq-devel': '/opt/wine-devel/bin/wine',
    'winehq-staging': '/opt/wine-staging/bin/wine',
    'wine-development': '/usr/lib/wine-development/wine',
    'system': 'wine',
}


def set_regedit(path, key, value='', type='REG_SZ', wine_path=None,
                prefix=None, arch='win32'):
    """Add keys to the windows registry.

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
        """ % (path, key, formatted_value[type])))
    reg_file.close()
    set_regedit_file(reg_path, wine_path=wine_path, prefix=prefix, arch=arch)
    os.remove(reg_path)


def set_regedit_file(filename, wine_path=None, prefix=None, arch='win32'):
    """Apply a regedit file to the Windows registry."""
    wineexec('regedit', args="/S '%s'" % (filename), wine_path=wine_path, prefix=prefix,
             arch=arch, blocking=True)


def delete_registry_key(key, wine_path=None, prefix=None, arch='win32'):
    wineexec('regedit', args='/S /D "%s"' % key, wine_path=wine_path,
             prefix=prefix, arch=arch, blocking=True)


def create_prefix(prefix, wine_path=None, arch='win32'):
    """Create a new Wine prefix."""
    logger.debug("Creating a %s prefix in %s", arch, prefix)

    # Avoid issue of 64bit Wine refusing to create win32 prefix
    # over an existing empty folder.
    if os.path.isdir(prefix) and not os.listdir(prefix):
        os.rmdir(prefix)

    if not wine_path:
        wine_path = wine().get_executable()

    wineboot_path = os.path.join(os.path.dirname(wine_path), 'wineboot')

    env = {
        'WINEARCH': arch,
        'WINEPREFIX': prefix
    }
    system.execute([wineboot_path], env=env)
    if not os.path.exists(os.path.join(prefix, 'system.reg')):
        logger.error('No system.reg found after prefix creation. '
                     'Prefix might not be valid')
    logger.info('%s Prefix created in %s', arch, prefix)

    if prefix:
        disable_desktop_integration(prefix)


def wineexec(executable, args="", wine_path=None, prefix=None, arch=None,
             working_dir=None, winetricks_wine='', blocking=False):
    """Execute a Wine command."""
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
        executable = '%s' % executable

    # Create prefix if necessary
    if not detected_arch:
        wine_bin = winetricks_wine if winetricks_wine else wine_path
        create_prefix(prefix, wine_path=wine_bin, arch=arch)

    env = {
        'WINEARCH': arch
    }
    if winetricks_wine:
        env['WINE'] = winetricks_wine
    else:
        env['WINE'] = wine_path
    if prefix:
        env['WINEPREFIX'] = prefix

    if settings.RUNNER_DIR in wine_path:
        env['LD_LIBRARY_PATH'] = ':'.join(runtime.get_paths())

    command = [wine_path]
    if executable:
        command.append(executable)
    command += shlex.split(args)
    if blocking:
        return system.execute(command, env=env, cwd=working_dir)
    else:
        thread = LutrisThread(command, runner=wine(), env=env, cwd=working_dir)
        thread.start()
        return thread


def winetricks(app, prefix=None, silent=True, wine_path=None):
    """Execute winetricks."""
    winetricks_path = os.path.join(datapath.get(), 'bin/winetricks')
    arch = detect_prefix_arch(prefix) or 'win32'
    if wine_path:
        winetricks_wine = wine_path
    else:
        winetricks_wine = wine().get_executable()
    args = app
    if str(silent).lower() in ('yes', 'on', 'true'):
        args = "-q " + args
    return wineexec(None, prefix=prefix, winetricks_wine=winetricks_wine,
                    wine_path=winetricks_path, arch=arch, args=args)


def winecfg(wine_path=None, prefix=None, arch='win32', blocking=True):
    """Execute winecfg."""
    if not wine_path:
        logger.debug("winecfg: Reverting to default wine")
        wine_path = wine().get_executable()

    winecfg_path = os.path.join(os.path.dirname(wine_path), "winecfg")
    logger.debug("winecfg: %s", winecfg_path)

    env = []
    if prefix:
        env.append('WINEPREFIX="%s" ' % prefix)
    env.append('WINEARCH="%s" ' % arch)

    if settings.RUNNER_DIR in wine_path:
        runtime32_path = os.path.join(settings.RUNTIME_DIR, "lib32")
        env.append('LD_LIBRARY_PATH={}'.format(runtime32_path))

    command = '{0} "{1}"'.format(' '.join(env), winecfg_path)
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    if blocking:
        p.communicate()


def joycpl(wine_path=None, prefix=None):
    """Execute Joystick control panel."""
    arch = detect_prefix_arch(prefix) or 'win32'
    wineexec('control', prefix=prefix,
             wine_path=wine_path, arch=arch, args='joy.cpl')


def eject_disc(wine_path, prefix):
    wineexec('eject', prefix=prefix, wine_path=wine_path, args='-a')


def detect_prefix_arch(directory=None):
    """Return the architecture of the prefix found in `directory`.

    If no `directory` given, return the arch of the system's default prefix.
    If no prefix found, return None."""
    if not directory:
        directory = "~/.wine"
    directory = os.path.expanduser(directory)
    registry_path = os.path.join(directory, 'system.reg')
    if not os.path.isdir(directory) or not os.path.isfile(registry_path):
        # No directory exists or invalid prefix
        logger.debug("No prefix found in %s", directory)
        return
    with open(registry_path, 'r') as registry:
        for i in range(5):
            line = registry.readline()
            if 'win64' in line:
                return 'win64'
            elif 'win32' in line:
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
    """Return the list of Wine versions installed"""
    if not os.path.exists(WINE_DIR):
        return []
    dirs = version_sort(os.listdir(WINE_DIR), reverse=True)
    return [dirname for dirname in dirs if is_version_installed(dirname)]


def get_wine_version_exe(version):
    if not version:
        version = get_default_version()
    if not version:
        raise RuntimeError("Wine is not installed")
    return os.path.join(WINE_DIR, '{}/bin/wine'.format(version))


def is_version_installed(version):
    return os.path.isfile(get_wine_version_exe(version))


def get_default_version():
    installed_versions = get_wine_versions()
    wine32_versions = [version for version in installed_versions if '64' not in version]
    if wine32_versions:
        return wine32_versions[0]
    if installed_versions:
        return installed_versions[0]


def get_system_wine_version(wine_path="wine"):
    """Return the version of Wine installed on the system."""
    if os.path.exists(wine_path) and os.path.isabs(wine_path):
        wine_stats = os.stat(wine_path)
        if wine_stats.st_size < 2000:
            # This version is a script, ignore it
            return
    try:
        version = subprocess.check_output([wine_path, "--version"]).decode().strip()
    except OSError:
        return
    else:
        if version.startswith('wine-'):
            version = version[5:]
        return version


def support_legacy_version(version):
    """Since Lutris 0.3.7, wine version contains architecture and optional
    info. Call this to keep existing games compatible with previous
    configurations."""
    if not version:
        return
    if version not in ('custom', 'system') and '-' not in version:
        version += '-i386'
    return version


# pylint: disable=C0103
class wine(Runner):
    description = "Runs Windows games"
    human_name = "Wine"
    platform = 'Windows'
    multiple_versions = True
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
            'label': 'Wine prefix',
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

    reg_prefix = "HKEY_CURRENT_USER\Software\Wine"
    reg_keys = {
        "RenderTargetLockMode": r"%s\Direct3D" % reg_prefix,
        "Audio": r"%s\Drivers" % reg_prefix,
        "MouseWarpOverride": r"%s\DirectInput" % reg_prefix,
        "OffscreenRenderingMode": r"%s\Direct3D" % reg_prefix,
        "StrictDrawOrdering": r"%s\Direct3D" % reg_prefix,
        "Desktop": r"%s\Explorer" % reg_prefix,
        "WineDesktop": r"%s\Explorer\Desktops" % reg_prefix,
        "ShowCrashDialog": r"%s\WineDbg" % reg_prefix
    }

    core_processes = (
        'services.exe',
        'winedevice.exe',
        'plugplay.exe',
        'explorer.exe',
        'rpcss.exe',
        'rundll32.exe',
        'wineboot.exe',
    )

    def __init__(self, config=None):
        super(wine, self).__init__(config)
        self.context_menu_entries = [
            ('winecfg', "Wine configuration", self.run_winecfg),
            ('wine-regedit', "Wine registry", self.run_regedit),
            ('winetricks', 'Winetricks', self.run_winetricks),
            ('joycpl', 'Joystick Control Panel', self.run_joycpl),
        ]

        def get_wine_version_choices():
            versions = []
            labels = {
                'winehq-devel': 'WineHQ devel (%s)',
                'winehq-staging': 'WineHQ staging (%s)',
                'wine-development': 'Wine Development (%s)',
                'system': 'System (%s)',
            }
            for build in sorted(WINE_PATHS.keys()):
                version = get_system_wine_version(WINE_PATHS[build])
                if version:
                    versions.append((labels[build] % version, build))

            versions.append(
                ('Custom (select executable below)', 'custom')
            )
            versions += [(v, v) for v in get_wine_versions()]
            return versions

        self.runner_options = [
            {
                'option': 'version',
                'label': "Wine version",
                'type': 'choice',
                'choices': get_wine_version_choices,
                'default': get_default_version(),
                'help': ("The version of Wine used to launch the game.\n"
                         "Using the last version is generally recommended, "
                         "but some games work better on older versions.")
            },
            {
                'option': 'custom_wine_path',
                'label': "Custom Wine executable",
                'type': 'file',
                'help': ('The Wine executable to be used if you have '
                         'selected "Custom" as the Wine version.')
            },
            {
                'option': 'xinput',
                'label': 'Enable Xinput (experimental)',
                'type': 'bool',
                'default': False,
                'help': ("Preloads a library that enables Joypads on games\n"
                         "using XInput.")
            },
            {
                'option': 'Desktop',
                'label': 'Windowed (virtual desktop)',
                'type': 'bool',
                'default': False,
                'help': ("Run the whole Windows desktop in a window.\n"
                         "Otherwise, run it fullscreen.\n"
                         "This corresponds to Wine's Virtual Desktop option.")
            },
            {
                'option': 'WineDesktop',
                'label': 'Virtual desktop resolution',
                'type': 'choice_with_entry',
                'choices': display.get_resolutions,
                'default': '800x600',
                'help': ("The size of the virtual desktop in pixels.")
            },
            {
                'option': 'MouseWarpOverride',
                'label': 'Mouse Warp Override',
                'type': 'choice',
                'choices': [('Enable', 'enable'),
                            ('Disable', 'disable'),
                            ('Force', 'force')],
                'default': 'enable',
                'advanced': True,
                'help': (
                    "Override the default mouse pointer warping behavior\n"
                    "<b>Enable</b>: (Wine default) warp the pointer when the "
                    "mouse is exclusively acquired \n"
                    "<b>Disable</b>: never warp the mouse pointer \n"
                    "<b>Force</b>: always warp the pointer"
                )
            },
            {
                'option': 'OffscreenRenderingMode',
                'label': 'Offscreen Rendering Mode',
                'type': 'choice',
                'choices': [('FBO', 'fbo'),
                            ('BackBuffer', 'backbuffer')],
                'default': 'fbo',
                'advanced': True,
                'help': ("Select the offscreen rendering implementation.\n"
                         "<b>FBO</b>: (Wine default) Use framebuffer objects "
                         "for offscreen rendering \n"
                         "<b>Backbuffer</b>: Render offscreen render targets "
                         "in the backbuffer.")
            },
            {
                'option': 'StrictDrawOrdering',
                'label': "Strict Draw Ordering",
                'type': 'choice',
                'choices': [('Enabled', 'enabled'),
                            ('Disabled', 'disabled')],
                'default': 'disabled',
                'advanced': True,
                'help': ("This option ensures any pending drawing operations "
                         "are submitted to the driver, but at a significant "
                         "performance cost.")
            },
            {
                'option': 'RenderTargetLockMode',
                'label': 'Render Target Lock Mode',
                'type': 'choice',
                'choices': [('Disabled', 'disabled'),
                            ('ReadTex', 'readtex'),
                            ('ReadDraw', 'readdraw')],
                'default': 'readtex',
                'advanced': True,
                'help': (
                    "Select which mode is used for onscreen render targets:\n"
                    "<b>Disabled</b>: Disables render target locking \n"
                    "<b>ReadTex</b>: (Wine default) Reads by glReadPixels, "
                    "writes by drawing a textured quad \n"
                    "<b>ReadDraw</b>: Uses glReadPixels for reading and "
                    "writing"
                )
            },
            {
                'option': 'Audio',
                'label': 'Audio driver',
                'type': 'choice',
                'choices': [('Auto', 'auto'),
                            ('Alsa', 'alsa'),
                            ('OSS', 'oss'),
                            ('Jack', 'jack')],
                'default': 'auto',
                'help': ("Which audio backend to use.\n"
                         "By default, Wine automatically picks the right one "
                         "for your system. Alsa is the default for modern"
                         "Linux distributions.")
            },
            {
                'option': 'ShowCrashDialog',
                'label': 'Show crash dialogs',
                'type': 'bool',
                'default': False
            },
            {
                'option': 'show_debug',
                'label': 'Output debugging info',
                'type': 'choice',
                'choices': [('Disabled', '-all'),
                            ('Enabled', '')],
                'default': '-all',
                'advanced': True,
                'help': ("Output debugging information in the game log "
                         "(might affect performance)")
            }
        ]

    @property
    def prefix_path(self):
        prefix_path = self.game_config.get('prefix', '')
        if not prefix_path:
            prefix_path = os.environ.get('WINEPREFIX', '')
        return os.path.expanduser(prefix_path)

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
    def wine_arch(self):
        """Return the wine architecture.

        Get it from the config or detect it from the prefix"""
        arch = self.game_config.get('arch') or 'auto'
        if arch not in ('win32', 'win64'):
            arch = detect_prefix_arch(self.prefix_path) or 'win32'
        return arch

    def get_version(self, use_default=True):
        """Return the Wine version to use. use_default can be set to false to
        force the installation of a specific wine version"""
        runner_version = self.runner_config.get('version')
        runner_version = support_legacy_version(runner_version)
        if runner_version:
            return runner_version
        if use_default:
            return get_default_version()

    def get_executable(self, version=None):
        """Return the path to the Wine executable.
        A specific version can be specified if needed.
        """
        path = WINE_DIR
        custom_path = self.runner_config.get('custom_wine_path', '')
        if version is None:
            version = self.get_version()
        if not version:
            return

        if version in WINE_PATHS.keys():
            abs_path = system.find_executable(WINE_PATHS[version])
            if abs_path:
                return abs_path
            # Fall back on bundled Wine
            version = get_default_version()
        elif version == 'custom':
            if os.path.exists(custom_path):
                return custom_path
            version = get_default_version()

        return os.path.join(path, version, 'bin/wine')

    def is_installed(self, version=None, any_version=False):
        """Check if Wine is installed.
        If `any_version` is set to True, checks if any version of wine is available
        """
        if any_version:
            return len(get_wine_versions()) > 0
        executable = self.get_executable(version)
        if executable:
            return os.path.exists(executable)
        else:
            return False

    @classmethod
    def msi_exec(cls, msi_file, quiet=False, prefix=None, wine_path=None, working_dir=None, blocking=False):
        msi_args = "/i %s" % msi_file
        if quiet:
            msi_args += " /q"
        return wineexec("msiexec", args=msi_args, prefix=prefix,
                        wine_path=wine_path, working_dir=working_dir, blocking=blocking)

    def run_winecfg(self, *args):
        winecfg(wine_path=self.get_executable(), prefix=self.prefix_path,
                arch=self.wine_arch, blocking=False)

    def run_regedit(self, *args):
        wineexec("regedit", wine_path=self.get_executable(), prefix=self.prefix_path)

    def run_winetricks(self, *args):
        winetricks('', prefix=self.prefix_path, wine_path=self.get_executable())

    def run_joycpl(self, *args):
        joycpl(prefix=self.prefix_path, wine_path=self.get_executable())

    def set_wine_desktop(self, enable_desktop=False):
        path = self.reg_keys['Desktop']

        if enable_desktop:
            set_regedit(path, 'Desktop', 'WineDesktop',
                        wine_path=self.get_executable(),
                        prefix=self.prefix_path,
                        arch=self.wine_arch)
        else:
            delete_registry_key(path,
                                wine_path=self.get_executable(),
                                prefix=self.prefix_path,
                                arch=self.wine_arch)

    def set_regedit_keys(self):
        """Reset regedit keys according to config."""
        prefix = self.prefix_path
        enable_wine_desktop = False
        for key, path in self.reg_keys.items():
            value = self.runner_config.get(key) or 'auto'
            if not value or value == 'auto' and key != 'ShowCrashDialog':
                delete_registry_key(path, wine_path=self.get_executable(),
                                    prefix=prefix, arch=self.wine_arch)
            elif key in self.runner_config:
                if key == 'Desktop' and value is True:
                    enable_wine_desktop = True
                else:
                    if key == 'ShowCrashDialog':
                        if value is True:
                            value = '00000001'
                        else:
                            value = '00000000'
                        type = 'REG_DWORD'
                    else:
                        type = 'REG_SZ'
                    set_regedit(path, key, value, type=type,
                                wine_path=self.get_executable(), prefix=prefix,
                                arch=self.wine_arch)
        self.set_wine_desktop(enable_wine_desktop)
        overrides = self.runner_config.get('overrides') or {}
        overrides_path = "%s\DllOverrides" % self.reg_prefix
        for dll, value in overrides.items():
            set_regedit(overrides_path, dll, value,
                        wine_path=self.get_executable(),
                        prefix=prefix, arch=self.wine_arch)

    def prelaunch(self):
        self.set_regedit_keys()
        return True

    def get_env(self, full=True):
        if full:
            env = os.environ.copy()
        else:
            env = {}
        env['WINEDEBUG'] = self.runner_config['show_debug']
        env['WINEARCH'] = self.wine_arch
        env['WINE'] = self.get_executable()
        if self.prefix_path:
            env['WINEPREFIX'] = self.prefix_path
        return env

    def get_pids(self, wine_path=None):
        """Return a list of pids of processes using the current wine exe."""
        if wine_path:
            exe = wine_path
        else:
            exe = self.get_executable()
        if not exe.startswith('/'):
            exe = system.find_executable(exe)
        pids = system.get_pids_using_file(exe)
        if self.wine_arch == 'win64':
            wine64 = exe + '64'
            pids_64 = system.get_pids_using_file(wine64)
            pids = pids | pids_64
        return pids

    def get_xinput_path(self):
        xinput_path = os.path.join(settings.RUNTIME_DIR,
                                   'lib32/koku-xinput-wine/koku-xinput-wine.so')
        if os.path.exists(xinput_path):
            return xinput_path

    def play(self):
        game_exe = self.game_exe
        arguments = self.game_config.get('args') or ''

        if not os.path.exists(game_exe):
            return {'error': 'FILE_NOT_FOUND', 'file': game_exe}

        launch_info = {}
        launch_info['env'] = self.get_env(full=False)

        if self.runner_config.get('xinput'):
            xinput_path = self.get_xinput_path()
            if xinput_path:
                logger.debug('Preloading %s', xinput_path)
                launch_info['ld_preload'] = self.get_xinput_path()
            else:
                logger.error('Missing koku-xinput-wine.so, Xinput won\'t be enabled')

        command = [self.get_executable()]
        if game_exe.endswith(".msi"):
            command.append('msiexec')
            command.append('/i')
        if game_exe.endswith('.lnk'):
            command.append('start')
            command.append('/unix')
        command.append(game_exe)

        if arguments:
            for arg in shlex.split(arguments):
                command.append(arg)
        launch_info['command'] = command
        return launch_info

    def stop(self):
        """The kill command runs wineserver -k."""
        wine_path = self.get_executable()
        wine_root = os.path.dirname(wine_path)
        env = self.get_env()
        command = [os.path.join(wine_root, "wineserver"), "-k"]
        logger.debug("Killing all wine processes: %s" % command)
        try:
            proc = subprocess.Popen(command, env=env)
            proc.wait()
        except OSError:
            logger.exception('Could not terminate wineserver %s', command)

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
