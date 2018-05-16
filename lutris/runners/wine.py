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
from lutris.util.strings import version_sort, parse_version
from lutris.util.wineprefix import WinePrefixManager
from lutris.util.x360ce import X360ce
from lutris.util.dxvk import DXVKManager
from lutris.runners.runner import Runner
from lutris.thread import LutrisThread
from lutris.gui.dialogs import FileDialog

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
MIN_SAFE_VERSION = '3.0'  # Wine installers must run with at least this version
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
    See: https://wiki.winehq.org/Wine_User%27s_Guide#WINEDLLOVERRIDES.3DDLL_Overrides
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
    if arch == 'win64' and wine_path and os.path.exists(wine_path + '64'):
        # Use wine64 by default if set to a 64bit prefix. Using regular wine
        # will prevent some registry keys from being created. Most likely to be
        # a bug in Wine. see: https://github.com/lutris/lutris/issues/804
        wine_path = wine_path + '64'

    wineexec('regedit',
             args="/S '%s'" % filename,
             wine_path=wine_path,
             prefix=prefix,
             arch=arch,
             blocking=True)


def delete_registry_key(key, wine_path=None, prefix=None, arch='win32'):
    wineexec('regedit', args='/S /D "%s"' % key, wine_path=wine_path,
             prefix=prefix, arch=arch, blocking=True)


def create_prefix(prefix, wine_path=None, arch='win32', overrides={},
                  install_gecko=None, install_mono=None):
    """Create a new Wine prefix."""
    logger.debug("Creating a %s prefix in %s", arch, prefix)

    # Avoid issue of 64bit Wine refusing to create win32 prefix
    # over an existing empty folder.
    if os.path.isdir(prefix) and not os.listdir(prefix):
        os.rmdir(prefix)

    if not wine_path:
        wine_path = wine().get_executable()
    if not wine_path:
        logger.error("Wine not found, can't create prefix")
        return
    wineboot_path = os.path.join(os.path.dirname(wine_path), 'wineboot')
    if not system.path_exists(wineboot_path):
        logger.error("No wineboot executable found in %s, "
                     "your wine installation is most likely broken", wine_path)
        return

    if install_gecko is 'False':
        overrides['mshtml'] = 'disabled'
    if install_mono is 'False':
        overrides['mscoree'] = 'disabled'

    wineenv = {
        'WINEARCH': arch,
        'WINEPREFIX': prefix,
        'WINEDLLOVERRIDES': get_overrides_env(overrides)
    }

    system.execute([wineboot_path], env=wineenv)
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


def winekill(prefix, arch='win32', wine_path=None, env=None, initial_pids=None):
    """Kill processes in Wine prefix."""

    initial_pids = initial_pids or []

    if not wine_path:
        wine_path = wine().get_executable()
    wine_root = os.path.dirname(wine_path)
    if not env:
        env = {
            'WINEARCH': arch,
            'WINEPREFIX': prefix
        }
    command = [os.path.join(wine_root, "wineserver"), "-k"]

    logger.debug("Killing all wine processes: %s" % command)
    logger.debug("\tWine prefix: %s", prefix)
    logger.debug("\tWine arch: %s", arch)
    if initial_pids:
        logger.debug("\tInitial pids: %s", initial_pids)

    system.execute(command, env=env, quiet=True)

    logger.debug("Waiting for wine processes to terminate")
    # Wineserver needs time to terminate processes
    num_cycles = 0
    while True:
        num_cycles += 1
        running_processes = [
            pid for pid in initial_pids
            if os.path.exists("/proc/%s" % pid)
        ]

        if not running_processes:
            break
        if num_cycles > 20:
            logger.warning("Some wine processes are still running: %s",
                           ', '.join(running_processes))
            break
        time.sleep(0.1)


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
    executable = str(executable) if executable else ''
    if not wine_path:
        wine_path = wine().get_executable()
    if not wine_path:
        raise RuntimeError("Wine is not installed")

    if not working_dir:
        if os.path.isfile(executable):
            working_dir = os.path.dirname(executable)

    executable, _args, working_dir = get_real_executable(executable, working_dir)
    if _args:
        args = '{} "{}"'.format(_args[0], _args[1])

    # Create prefix if necessary
    if arch not in ('win32', 'win64'):
        arch = detect_arch(prefix, wine_path)
    if not detect_prefix_arch(prefix):
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

    if use_lutris_runtime(
            wine_path=executable,
            force_disable=disable_runtime or wine_config.system_config['disable_runtime']
    ):
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
    if wine_path:
        winetricks_wine = wine_path
    else:
        winetricks_wine = wine().get_executable()
    if arch not in ('win32', 'win64'):
        arch = detect_arch(prefix, winetricks_wine)
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
    arch = detect_arch(prefix, wine_path)
    wineexec('control', prefix=prefix,
             wine_path=wine_path, arch=arch, args='joy.cpl')


def eject_disc(wine_path, prefix):
    wineexec('eject', prefix=prefix, wine_path=wine_path, args='-a')


def detect_arch(prefix_path=None, wine_path=None):
    arch = detect_prefix_arch(prefix_path)
    if arch:
        return arch
    if wine_path and os.path.exists(wine_path + '64'):
        return 'win64'
    else:
        return 'win32'


def detect_prefix_arch(prefix_path=None):
    """Return the architecture of the prefix found in `prefix_path`.

    If no `prefix_path` given, return the arch of the system's default prefix.
    If no prefix found, return None."""
    if not prefix_path:
        prefix_path = "~/.wine"
    prefix_path = os.path.expanduser(prefix_path)
    registry_path = os.path.join(prefix_path, 'system.reg')
    if not os.path.isdir(prefix_path) or not os.path.isfile(registry_path):
        # No prefix_path exists or invalid prefix
        logger.debug("No prefix found in %s", prefix_path)
        return
    with open(registry_path, 'r') as registry:
        for i in range(5):
            line = registry.readline()
            if 'win64' in line:
                return 'win64'
            elif 'win32' in line:
                return 'win32'
    logger.debug("Can't detect prefix arch for %s", prefix_path)


def set_drive_path(prefix, letter, path):
    dosdevices_path = os.path.join(prefix, "dosdevices")
    if not os.path.exists(dosdevices_path):
        raise OSError("Invalid prefix path %s" % prefix)
    drive_path = os.path.join(dosdevices_path, letter + ":")
    if os.path.exists(drive_path):
        os.remove(drive_path)
    logger.debug("Linking %s to %s", drive_path, path)
    os.symlink(path, drive_path)


def use_lutris_runtime(wine_path, force_disable=False):
    """Returns whether to use the Lutris runtime.
    The runtime can be forced to be disabled, otherwise it's disabled
    automatically if Wine is installed system wide.
    """
    if force_disable or runtime.RUNTIME_DISABLED:
        return False
    if WINE_DIR in wine_path:
        logger.debug("%s is provided by Lutris, using runtime")
        return True
    return not is_installed_systemwide()


def is_installed_systemwide():
    """Return whether Wine is installed outside of Lutris"""
    for build in WINE_PATHS.keys():
        if system.find_executable(WINE_PATHS[build]):
            return True
    return False


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
    """Return the default version of wine. Prioritize 64bit builds"""
    installed_versions = get_wine_versions()
    wine64_versions = [version for version in installed_versions if '64' in version]
    if wine64_versions:
        return wine64_versions[0]
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

    system_options_override = [
        {
            'option': 'disable_runtime',
            'default': is_installed_systemwide(),
        }
    ]

    reg_prefix = "HKEY_CURRENT_USER/Software/Wine"
    reg_keys = {
        "RenderTargetLockMode": r"%s/Direct3D" % reg_prefix,
        "MouseWarpOverride": r"%s/DirectInput" % reg_prefix,
        "OffscreenRenderingMode": r"%s/Direct3D" % reg_prefix,
        "StrictDrawOrdering": r"%s/Direct3D" % reg_prefix,
        "Desktop": r"%s/Explorer" % reg_prefix,
        "WineDesktop": r"%s/Explorer/Desktops" % reg_prefix,
        "ShowCrashDialog": r"%s/WineDbg" % reg_prefix,
        "UseXVidMode": r"%s/X11 Driver" % reg_prefix
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
        self.dll_overrides = {}
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
                'option': 'dxvk',
                'label': 'Enable DXVK',
                'type': 'bool',
                'help': 'Use DXVK to translate DirectX 11 calls to Vulkan'
            },
            {
                'option': 'x360ce-path',
                'label': "Path to the game's executable, for x360ce support",
                'type': 'directory_chooser',
                'help': "Locate the path for the game's executable for x360 support"
            },
            {
                'option': 'x360ce-dinput',
                'label': 'x360ce dinput 8 mode',
                'type': 'bool',
                'default': False,
                'help': "Configure x360ce with dinput8.dll, required for some games"
            },
            {
                'option': 'x360ce-xinput9',
                'label': 'x360ce xinput 9.1.0 mode',
                'type': 'bool',
                'default': False,
                'help': "Configure x360ce with xinput9_1_0.dll, required for some newer games"
            },
            {
                'option': 'dumbxinputemu',
                'label': 'Use Dumb xinput Emulator (experimental)',
                'type': 'bool',
                'default': False,
                'help': "Use the dlls from kozec/dumbxinputemu"
            },
            {
                'option': 'xinput-arch',
                'label': 'Xinput architecture',
                'type': 'choice',
                'choices': [('Same as wine prefix', ''),
                            ('32 bit', 'win32'),
                            ('64 bit', 'win64')],
                'default': ''
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
                'choices': display.get_unique_resolutions,
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
                'help': (
                    "This option ensures any pending drawing operations are "
                    "submitted to the driver, but at a significant performance "
                    "cost. Set to \"enabled\" to enable. This setting is deprecated "
                    "since wine-2.6 and will likely be removed after wine-3.0. "
                    "Use \"csmt\" instead."
                )
            },
            {
                'option': 'UseGLSL',
                'label': "Use GLSL",
                'type': 'choice',
                'choices': [('Enabled', 'enabled'),
                            ('Disabled', 'disabled')],
                'default': 'enabled',
                'advanced': True,
                'help': (
                    "When set to \"disabled\", this disables the use of GLSL for shaders. "
                    "In general disabling GLSL is not recommended, "
                    "only use this for debugging purposes."
                )
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
                'option': 'UseXVidMode',
                'label': 'Use XVidMode to switch resolutions',
                'type': 'bool',
                'default': False,
                'advanced': True,
                'help': (
                    'Set this to "Y" to allow wine switch the resolution using XVidMode extension.'
                )
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
                            ('Show FPS', '+fps'),
                            ('Full (CAUTION: Will cause MASSIVE slowdown)', '+all')],
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
            {
                'option': 'sandbox',
                'type': 'bool',
                'label': 'Create a sandbox for wine folders',
                'default': True,
                'help': ("Do not use $HOME for desktop integration folders.\n"
                         "By default, it use the directories in the confined "
                         "Windows environment.")
            },
            {
                'option': 'sandbox_dir',
                'type': 'directory_chooser',
                'label': 'Sandbox directory',
                'help': ("Custom directory for desktop integration folders.")
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
            arch = detect_arch(self.prefix_path, self.get_executable())
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
            wine_path = self.get_path_for_version(default_version)
            if wine_path:
                # Update the version in the config
                if version == self.runner_config.get('version'):
                    self.runner_config['version'] = default_version
                    # TODO: runner_config is a dict so we have to instanciate a
                    # LutrisConfig object to save it.
                    # XXX: The version key could be either in the game specific
                    # config or the runner specific config. We need to know
                    # which one to get the correct LutrisConfig object.
            return wine_path

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Check if Wine is installed.
        If no version is passed, checks if any version of wine is available
        """
        if not version:
            wine_versions = get_wine_versions()
            if min_version:
                min_version_list, _, _ = parse_version(min_version)
                for version in wine_versions:
                    version_list, _, _ = parse_version(version)
                    if version_list > min_version_list:
                        return True
                logger.warning("Wine %s or higher not found", min_version)
            return bool(wine_versions)
        return system.path_exists(self.get_executable(version, fallback))

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
        winetricks('', prefix=self.prefix_path, wine_path=self.get_executable(), config=self)

    def run_joycpl(self, *args):
        joycpl(prefix=self.prefix_path, wine_path=self.get_executable(), config=self)

    def set_wine_desktop(self, enable_desktop=False):
        prefix = self.prefix_path
        prefix_manager = WinePrefixManager(prefix)
        path = self.reg_keys['Desktop']

        if enable_desktop:
            prefix_manager.set_registry_key(path, 'Desktop', 'WineDesktop')
        else:
            prefix_manager.clear_registry_key(path)

    def set_regedit_keys(self):
        """Reset regedit keys according to config."""
        prefix = self.prefix_path
        enable_wine_desktop = False
        prefix_manager = WinePrefixManager(prefix)
        # Those options are directly changed with the prefix manager and skip
        # any calls to regedit.
        managed_keys = {
            'ShowCrashDialog': prefix_manager.set_crash_dialogs,
            'UseXVidMode': prefix_manager.use_xvid_mode
        }

        for key, path in self.reg_keys.items():
            value = self.runner_config.get(key) or 'auto'
            if not value or value == 'auto' and key not in managed_keys.keys():
                prefix_manager.clear_registry_key(path)
            elif key in self.runner_config:
                if key == 'Desktop' and value is True:
                    enable_wine_desktop = True
                    continue
                elif key in managed_keys.keys():
                    # Do not pass fallback 'auto' value to managed keys
                    if value == 'auto':
                        value = None
                    managed_keys[key](value)
                    continue
                prefix_manager.set_registry_key(path, key, value)

        self.set_wine_desktop(enable_wine_desktop)

    def toggle_dxvk(self, enable_dxvk):
        dxvk_manager = DXVKManager(self.prefix_path, arch=self.wine_arch)
        if enable_dxvk:
            if not dxvk_manager.is_available():
                dxvk_manager.download()
            dxvk_manager.enable()
            for dll in dxvk_manager.dxvk_dlls:
                self.dll_overrides[dll] = 'n'
        else:
            dxvk_manager.disable()

    def prelaunch(self):
        if not os.path.exists(os.path.join(self.prefix_path, 'user.reg')):
            create_prefix(self.prefix_path, arch=self.wine_arch)
        prefix_manager = WinePrefixManager(self.prefix_path)
        prefix_manager.configure_joypads()
        self.sandbox(prefix_manager)
        self.set_regedit_keys()
        self.setup_x360ce(self.runner_config.get('x360ce-path'))
        self.toggle_dxvk(bool(self.runner_config.get('dxvk')))
        return True

    def get_dll_overrides(self):
        overrides = self.runner_config.get('overrides') or {}

        overrides.update(self.dll_overrides)
        return overrides

    def get_env(self, os_env=True):
        env = super(wine, self).get_env(os_env)
        env['WINEDEBUG'] = self.runner_config.get('show_debug', '-all')
        env['WINEARCH'] = self.wine_arch
        env['WINE'] = self.get_executable()
        if self.prefix_path:
            env['WINEPREFIX'] = self.prefix_path

        overrides = self.get_dll_overrides()
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

    def setup_x360ce(self, x360ce_path):
        if not x360ce_path:
            return
        x360ce_path = os.path.expanduser(x360ce_path)
        if not os.path.isdir(x360ce_path):
            logger.error("%s is not a valid path for x360ce", x360ce_path)
            return
        mode = 'dumbxinputemu' if self.runner_config.get('dumbxinputemu') else 'x360ce'
        dll_files = ['xinput1_3.dll']
        if self.runner_config.get('x360ce-xinput9'):
            dll_files.append('xinput9_1_0.dll')

        for dll_file in dll_files:
            xinput_dest_path = os.path.join(x360ce_path, dll_file)
            xinput_arch = self.runner_config.get('xinput-arch') or self.wine_arch
            dll_path = os.path.join(datapath.get(), 'controllers/{}-{}'.format(mode, xinput_arch))
            if not os.path.exists(xinput_dest_path):
                source_file = dll_file if mode == 'dumbxinputemu' else 'xinput1_3.dll'
                shutil.copyfile(os.path.join(dll_path, source_file), xinput_dest_path)

        if mode == 'x360ce':
            if self.runner_config.get('x360ce-dinput'):
                dinput8_path = os.path.join(dll_path, 'dinput8.dll')
                dinput8_dest_path = os.path.join(x360ce_path, 'dinput8.dll')
                shutil.copyfile(dinput8_path, dinput8_dest_path)

            x360ce_config = X360ce()
            x360ce_config.populate_controllers()
            x360ce_config.write(os.path.join(x360ce_path, 'x360ce.ini'))

        # X360 DLL handling
        self.dll_overrides['xinput1_3'] = 'native'
        if self.runner_config.get('x360ce-xinput9'):
            self.dll_overrides['xinput9_1_0'] = 'native'
        if self.runner_config.get('x360ce-dinput'):
            self.dll_overrides['dinput8'] = 'native'

    def sandbox(self, wine_prefix):
        sandbox = self.runner_config.get('sandbox', True)

        if (sandbox):
            sandbox_dir = self.runner_config.get('sandbox_dir', None)
            wine_prefix.desktop_integration(desktop_dir=sandbox_dir)

    def play(self):
        game_exe = self.game_exe
        arguments = self.game_config.get('args', '')

        if not os.path.exists(game_exe):
            return {'error': 'FILE_NOT_FOUND', 'file': game_exe}

        launch_info = {}
        launch_info['env'] = self.get_env(os_env=False)

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
        winekill(self.prefix_path,
                 arch=self.wine_arch,
                 wine_path=self.get_executable(),
                 env=self.get_env(),
                 initial_pids=self.get_pids())
        return True

    @staticmethod
    def parse_wine_path(path, prefix_path=None):
        """Take a Windows path, return the corresponding Linux path."""
        if not prefix_path:
            prefix_path = os.path.expanduser("~/.wine")

        path = path.replace("\\\\", "/").replace('\\', '/')

        if path[1] == ':':  # absolute path
            drive = os.path.join(prefix_path, 'dosdevices', path[:2].lower())
            if os.path.islink(drive):  # Try to resolve the path
                drive = os.readlink(drive)
            return os.path.join(drive, path[3:])

        elif path[0] == '/':  # drive-relative path. C is as good a guess as any..
            return os.path.join(prefix_path, 'drive_c', path[1:])

        else:  # Relative path
            return path
