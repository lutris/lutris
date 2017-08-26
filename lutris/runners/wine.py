import os
import time
import shlex
import shutil
import subprocess
from collections import OrderedDict

from lutris import runtime
from lutris import settings
from lutris.config import LutrisConfig
from lutris.util import datapath, display, system
from lutris.util.log import logger
from lutris.util.strings import version_sort
from lutris.util.wineprefix import WinePrefixManager
from lutris.util.x360ce import X360ce
from lutris.runners.runner import Runner
from lutris.thread import LutrisThread
from lutris.gui.dialogs import FileDialog

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
    reg_file.write(
        'REGEDIT4\n\n[%s]\n"%s"=%s\n' % (path, key, formatted_value[type])
    )
    reg_file.close()
    set_regedit_file(reg_path, wine_path=wine_path, prefix=prefix, arch=arch)
    os.remove(reg_path)


def get_overrides_env(overrides):
    """
    Output a string of dll overrides usable with WINEDLLOVERRIDES
    See: https://www.winehq.org/docs/wineusr-guide/x258#AEN309
    """
    if not overrides:
        return ''
    override_buckets = OrderedDict([
        ('n,b', []),
        ('b,n', []),
        ('b', []),
        ('n', []),
        ('', [])
    ])
    for dll, value in overrides.items():
        if not value:
            value = ''
        value = value.replace(' ', '')
        value = value.replace('builtin', 'b')
        value = value.replace('native', 'n')
        value = value.replace('disabled', '')
        try:
            override_buckets[value].append(dll)
        except KeyError:
            logger.error('Invalid override value %s', value)
            continue

    override_strings = []
    for value, dlls in override_buckets.items():
        if not dlls:
            continue
        override_strings.append("{}={}".format(','.join(sorted(dlls)), value))
    return ';'.join(override_strings)


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
    if not system.path_exists(wineboot_path):
        logger.error("No wineboot executable found in %s, your wine installation is most likely broken", wine_path)
        return

    env = {
        'WINEARCH': arch,
        'WINEPREFIX': prefix
    }
    system.execute([wineboot_path], env=env)
    for i in range(20):
        time.sleep(.25)
        if os.path.exists(os.path.join(prefix, 'user.reg')):
            break
    if not os.path.exists(os.path.join(prefix, 'user.reg')):
        logger.error('No user.reg found after prefix creation. '
                     'Prefix might not be valid')
        return
    logger.info('%s Prefix created in %s', arch, prefix)
    prefix_manager = WinePrefixManager(prefix)
    prefix_manager.setup_defaults()


def wineexec(executable, args="", wine_path=None, prefix=None, arch=None,
             working_dir=None, winetricks_wine='', blocking=False,
             config=None, include_processes=[], exclude_processes=[],
             disable_runtime=False, env={}, overrides=None):
    """
    Execute a Wine command.

    Args:
        executable (str): wine program to run, pass None to run wine itself
        args (str): program arguments
        wine_path (str): path to the wine version to use
        prefix (str): path to the wine prefix to use
        arch (str): wine architecture of the prefix
        working_dir (str): path to the working dir for the process
        winetricks_wine (str): path to the wine version used by winetricks
        blocking (bool): if true, do not run the process in a thread
        config (LutrisConfig): LutrisConfig object for the process context
        watch (list): list of process names to monitor (even when in a ignore list)

    Returns:
        Process results if the process is running in blocking mode or
        LutrisThread instance otherwise.
    """
    detected_arch = detect_prefix_arch(prefix)
    executable = str(executable) if executable else ''
    if arch not in ('win32', 'win64'):
        arch = detected_arch or 'win32'
    if not wine_path:
        wine_path = wine().get_executable()
    if not working_dir:
        if os.path.isfile(executable):
            working_dir = os.path.dirname(executable)

    executable, _args, working_dir = get_real_executable(executable, working_dir)
    if _args:
        args = '{} "{}"'.format(_args[0], _args[1])

    # Create prefix if necessary
    if not detected_arch:
        wine_bin = winetricks_wine if winetricks_wine else wine_path
        create_prefix(prefix, wine_path=wine_bin, arch=arch)

    wineenv = {
        'WINEARCH': arch
    }
    if winetricks_wine:
        wineenv['WINE'] = winetricks_wine
    else:
        wineenv['WINE'] = wine_path
    if prefix:
        wineenv['WINEPREFIX'] = prefix

    wine_config = config or LutrisConfig(runner_slug='wine')
    if (not wine_config.system_config['disable_runtime'] and
            not runtime.is_disabled() and not disable_runtime):
        wineenv['LD_LIBRARY_PATH'] = ':'.join(runtime.get_paths())

    if overrides:
        wineenv['WINEDLLOVERRIDES'] = get_overrides_env(overrides)

    wineenv.update(env)

    command = [wine_path]
    if executable:
        command.append(executable)
    command += shlex.split(args)
    if blocking:
        return system.execute(command, env=wineenv, cwd=working_dir)
    else:
        thread = LutrisThread(command, runner=wine(), env=wineenv, cwd=working_dir,
                              include_processes=include_processes,
                              exclude_processes=exclude_processes)
        thread.start()
        return thread


def winetricks(app, prefix=None, arch=None, silent=True,
               wine_path=None, config=None, disable_runtime=False):
    """Execute winetricks."""
    winetricks_path = os.path.join(datapath.get(), 'bin/winetricks')
    if arch not in ('win32', 'win64'):
        arch = detect_prefix_arch(prefix) or 'win32'
    if wine_path:
        winetricks_wine = wine_path
    else:
        winetricks_wine = wine().get_executable()
    args = app
    if str(silent).lower() in ('yes', 'on', 'true'):
        args = "--unattended " + args
    return wineexec(None, prefix=prefix, winetricks_wine=winetricks_wine,
                    wine_path=winetricks_path, arch=arch, args=args,
                    config=config, disable_runtime=disable_runtime)


def winecfg(wine_path=None, prefix=None, arch='win32', config=None):
    """Execute winecfg."""
    if not wine_path:
        logger.debug("winecfg: Reverting to default wine")
        wine_path = wine().get_executable()

    winecfg_path = os.path.join(os.path.dirname(wine_path), "winecfg")
    logger.debug("winecfg: %s", winecfg_path)

    return wineexec(None, prefix=prefix, winetricks_wine=winecfg_path,
                    wine_path=winecfg_path, arch=arch, config=config,
                    include_processes=['winecfg.exe'])


def joycpl(wine_path=None, prefix=None, config=None):
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
    versions = []

    for build in sorted(WINE_PATHS.keys()):
        version = get_system_wine_version(WINE_PATHS[build])
        if version:
            versions.append(build)

    if os.path.exists(WINE_DIR):
        dirs = version_sort(os.listdir(WINE_DIR), reverse=True)
        for dirname in dirs:
            if is_version_installed(dirname):
                versions.append(dirname)
    return versions


def get_wine_version_exe(version):
    if not version:
        version = get_default_version()
    if not version:
        raise RuntimeError("Wine is not installed")
    return os.path.join(WINE_DIR, '{}/bin/wine'.format(version))


def is_version_installed(version):
    return os.path.isfile(get_wine_version_exe(version))


def get_default_version():
    """Return the default version of wine. Prioritize 32bit builds"""
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


def get_real_executable(windows_executable, working_dir=None):
    """Given a Windows executable, return the real program
    capable of launching it along with necessary arguments."""

    exec_name = windows_executable.lower()

    if exec_name.endswith(".msi"):
        return ('msiexec', ['/i', windows_executable], working_dir)

    if exec_name.endswith(".bat"):
        if not working_dir or os.path.dirname(windows_executable) == working_dir:
            working_dir = os.path.dirname(windows_executable) or None
            windows_executable = os.path.basename(windows_executable)
        return ('cmd', ['/C', windows_executable], working_dir)

    if exec_name.endswith(".lnk"):
        return ('start', ['/unix', windows_executable], working_dir)

    return (windows_executable, [], working_dir)


# pylint: disable=C0103
class wine(Runner):
    description = "Runs Windows games"
    human_name = "Wine"
    platforms = ['Windows']
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
            ('wineexec', "Run EXE inside wine prefix", self.run_wineexec),
            ('winecfg', "Wine configuration", self.run_winecfg),
            ('wine-regedit', "Wine registry", self.run_regedit),
            ('winetricks', 'Winetricks', self.run_winetricks),
            ('joycpl', 'Joystick Control Panel', self.run_joycpl),
        ]

        def get_wine_version_choices():
            version_choices = [
                ('Custom (select executable below)', 'custom')
            ]
            labels = {
                'winehq-devel': 'WineHQ devel ({})',
                'winehq-staging': 'WineHQ staging ({})',
                'wine-development': 'Wine Development ({})',
                'system': 'System ({})',
            }
            versions = get_wine_versions()
            for version in versions:
                if version in labels.keys():
                    version_number = get_system_wine_version(WINE_PATHS[version])
                    label = labels[version].format(version_number)
                else:
                    label = version
                version_choices.append((label, version))
            return version_choices

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
                'label': 'Enable Koku-Xinput (experimental, try using the x360 option instead)',
                'type': 'bool',
                'default': False,
                'help': ("Preloads a library that enables Joypads on games\n"
                         "using XInput.")
            },
            {
                'option': 'x360ce-path',
                'label': "Path to the game's executable, for x360ce support",
                'type': 'directory_chooser',
                'help': "Locate the path for the game's executable for x360 support"
            },
            {
                'option': 'x360ce-dinput',
                'label': 'x360ce dinput mode',
                'type': 'bool',
                'default': False,
                'help': "Configure x360ce with dinput8.dll, required for some games such as Darksiders 1"
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
                'help': ("This option ensures any pending drawing operations are submitted to the driver, but at"
                         " a significant performance cost. Set to \"enabled\" to enable. This setting is deprecated"
                         " since wine-2.6 and will likely be removed after wine-3.0. Use \"csmt\" instead.""")
            },
            {
                'option': 'UseGLSL',
                'label': "Use GLSL",
                'type': 'choice',
                'choices': [('Enabled', 'enabled'),
                            ('Disabled', 'disabled')],
                'default': 'enabled',
                'advanced': True,
                'help': ("When set to \"disabled\", this disables the use of GLSL for shaders."
                         "In general disabling GLSL is not recommended, only use this for debugging purposes.")
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
                            ('Enabled', ''),
                            ('Full', '+all')],
                'default': '-all',
                'advanced': True,
                'help': ("Output debugging information in the game log "
                         "(might affect performance)")
            },
            {
                'option': 'overrides',
                'type': 'mapping',
                'label': 'DLL overrides',
                'advanced': True,
                'help': "Sets WINEDLLOVERRIDES when launching the game."
            },
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

    def get_path_for_version(self, version):
        if version in WINE_PATHS.keys():
            return system.find_executable(WINE_PATHS[version])
        elif version == 'custom':
            return self.runner_config.get('custom_wine_path', '')
        else:
            return os.path.join(WINE_DIR, version, 'bin/wine')

    def get_executable(self, version=None, fallback=True):
        """Return the path to the Wine executable.
        A specific version can be specified if needed.
        """
        if version is None:
            version = self.get_version()
        if not version:
            return

        wine_path = self.get_path_for_version(version)
        if os.path.exists(wine_path):
            return wine_path

        if fallback:
            # Fallback to default version
            default_version = get_default_version()
            logger.warning("No wine version %s found, falling back to %s",
                           version, default_version)
            return self.get_path_for_version(default_version)

    def is_installed(self, version=None, fallback=True):
        """Check if Wine is installed.
        If no version is passed, checks if any version of wine is available
        """
        if not version:
            return len(get_wine_versions()) > 0
        executable = self.get_executable(version, fallback)
        if executable:
            return os.path.exists(executable)
        else:
            return False

    @classmethod
    def msi_exec(cls, msi_file, quiet=False, prefix=None, wine_path=None,
                 working_dir=None, blocking=False):
        msi_args = "/i %s" % msi_file
        if quiet:
            msi_args += " /q"
        return wineexec("msiexec", args=msi_args, prefix=prefix,
                        wine_path=wine_path, working_dir=working_dir, blocking=blocking)

    def run_wineexec(self, *args):
        dlg = FileDialog("Select an EXE or MSI file", default_path=self.game_path)
        filename = dlg.filename
        if not filename:
            return
        wineexec(filename, wine_path=self.get_executable(), prefix=self.prefix_path, config=self)

    def run_winecfg(self, *args):
        winecfg(wine_path=self.get_executable(), prefix=self.prefix_path,
                arch=self.wine_arch, config=self)

    def run_regedit(self, *args):
        wineexec("regedit", wine_path=self.get_executable(), prefix=self.prefix_path, config=self)

    def run_winetricks(self, *args):
        winetricks('', prefix=self.prefix_path, wine_path=self.get_executable(), config=self, disable_runtime=True)

    def run_joycpl(self, *args):
        joycpl(prefix=self.prefix_path, wine_path=self.get_executable(), config=self)

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
        prefix_manager = WinePrefixManager(prefix)

        for key, path in self.reg_keys.items():
            value = self.runner_config.get(key) or 'auto'
            if not value or value == 'auto' and key != 'ShowCrashDialog':
                delete_registry_key(path, wine_path=self.get_executable(),
                                    prefix=prefix, arch=self.wine_arch)
            elif key in self.runner_config:
                if key == 'Desktop' and value is True:
                    enable_wine_desktop = True
                    continue
                elif key == 'ShowCrashDialog':
                    prefix_manager.set_crash_dialogs(value)
                    continue
                else:
                    type = 'REG_SZ'
                set_regedit(path, key, value, type=type,
                            wine_path=self.get_executable(), prefix=prefix,
                            arch=self.wine_arch)
        self.set_wine_desktop(enable_wine_desktop)

    def prelaunch(self):
        if not os.path.exists(os.path.join(self.prefix_path, 'user.reg')):
            create_prefix(self.prefix_path, arch=self.wine_arch)
        prefix_manager = WinePrefixManager(self.prefix_path)
        prefix_manager.setup_defaults()
        prefix_manager.configure_joypads()
        self.set_regedit_keys()
        return True

    def get_env(self, full=True):
        if full:
            env = os.environ.copy()
        else:
            env = {}
        env['WINEDEBUG'] = self.runner_config.get('show_debug', '-all')
        env['WINEARCH'] = self.wine_arch
        env['WINE'] = self.get_executable()
        if self.prefix_path:
            env['WINEPREFIX'] = self.prefix_path

        overrides = self.runner_config.get('overrides') or {}
        if self.runner_config.get('x360ce-path'):
            overrides['xinput1_3'] = 'native,builtin'
            if self.runner_config.get('x360ce-dinput'):
                overrides['dinput8'] = 'native,builtin'
        if overrides:
            env['WINEDLLOVERRIDES'] = get_overrides_env(overrides)

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
        if self.wine_arch == 'win64' and os.path.basename(exe) == 'wine':
            wine64 = exe + '64'
            pids_64 = system.get_pids_using_file(wine64)
            pids = pids | pids_64
        return pids

    def get_xinput_path(self):
        xinput_path = os.path.join(settings.RUNTIME_DIR,
                                   'lib32/koku-xinput-wine/koku-xinput-wine.so')
        if os.path.exists(xinput_path):
            return xinput_path

    def setup_x360ce(self, x360ce_path):
        if not os.path.isdir(x360ce_path):
            logger.error("%s is not a valid path for x360ce", x360ce_path)
            return
        xinput_dest_path = os.path.join(x360ce_path, 'xinput1_3.dll')
        dll_path = os.path.join(datapath.get(), 'controllers/x360ce-{}'.format(self.wine_arch))
        if not os.path.exists(xinput_dest_path):
            xinput1_3_path = os.path.join(dll_path, 'xinput1_3.dll')
            shutil.copyfile(xinput1_3_path, xinput_dest_path)
        if self.runner_config.get('x360ce-dinput') and self.wine_arch == 'win32':
            dinput8_path = os.path.join(dll_path, 'dinput8.dll')
            dinput8_dest_path = os.path.join(x360ce_path, 'dinput8.dll')
            shutil.copyfile(dinput8_path, dinput8_dest_path)

        x360ce_config = X360ce()
        x360ce_config.populate_controllers()
        x360ce_config.write(os.path.join(x360ce_path, 'x360ce.ini'))

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

        if self.runner_config.get('x360ce-path'):
            self.setup_x360ce(self.runner_config['x360ce-path'])

        command = [self.get_executable()]

        game_exe, _args, working_dir = get_real_executable(game_exe, self.working_dir)
        command.append(game_exe)
        if _args:
            command = command + _args

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
        if not prefix_path:
            prefix_path = os.path.expanduser("~/.wine")

        path = path.replace("\\\\", "/").replace('\\', '/')

        if path[1] == ':': # absolute path
            drive = os.path.join(prefix_path, 'dosdevices', path[:2].lower())
            if os.path.islink(drive): # Try to resolve the path
                drive = os.readlink(drive)
            return os.path.join(drive, path[3:])

        elif path[0] == '/': # drive-relative path. C is as good a guess as any..
            return os.path.join(prefix_path, 'drive_c', path[1:])

        else: # Relative path
            return path
