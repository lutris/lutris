"""Utilities for manipulating Wine"""
import os
import subprocess
from collections import OrderedDict

from lutris import runtime, settings
from lutris.gui.dialogs import DontShowAgainDialog, ErrorDialog
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import version_sort
from lutris.util.vulkan import vulkan_available
from lutris.runners.steam import steam

MIN_NUMBER_FILES_OPEN = 1048576
WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
WINE_PATHS = {
    'winehq-devel': '/opt/wine-devel/bin/wine',
    'winehq-staging': '/opt/wine-staging/bin/wine',
    'wine-development': '/usr/lib/wine-development/wine',
    'system': 'wine',
}

ESYNC_LIMIT_CHECK=os.environ.get('ESYNC_LIMIT_CHECK', '').lower()

def get_proton():
    """Get the Folder that contains all the Proton versions. Can probably be improved"""
    for path in [os.path.join(p,'common') for p in steam().get_steamapps_dirs() ]:
        if os.path.isdir(path):
            proton_versions = [p for p in os.listdir(path) if "Proton" in p]
            for version in proton_versions:
                if os.path.exists(os.path.join(path, version, 'dist/bin/wine')):
                    return path
    return None

PROTON_PATH = get_proton()

def detect_arch(prefix_path=None, wine_path=None):
    """Given a Wine prefix path, return its architecture"""
    arch = detect_prefix_arch(prefix_path)
    if arch:
        return arch
    if wine_path and os.path.exists(wine_path + '64'):
        return 'win64'
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
        logger.debug("Prefix not found: %s", prefix_path)
        return None
    with open(registry_path, 'r') as registry:
        for _line_no in range(5):
            line = registry.readline()
            if 'win64' in line:
                return 'win64'
            if 'win32' in line:
                return 'win32'
    logger.debug("Failed to detect Wine prefix architecture in %s", prefix_path)
    return None


def set_drive_path(prefix, letter, path):
    """Changes the path to a Wine drive"""
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
        logger.info("Runtime is forced disabled")
        return False
    if WINE_DIR in wine_path:
        logger.debug("%s is provided by Lutris, using runtime")
        return True
    if is_installed_systemwide():
        logger.info("Using system wine version, not using runtime")
        return False
    logger.debug("Using Lutris runtime for wine")
    return True


def is_installed_systemwide():
    """Return whether Wine is installed outside of Lutris"""
    for build in WINE_PATHS.values():
        if system.find_executable(build):
            if (
                    build == 'wine' and
                    os.path.exists('/usr/lib/wine/wine64') and
                    not os.path.exists('/usr/lib/wine/wine')
            ):
                logger.warning("wine32 is missing from system")
                return False
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

    if PROTON_PATH:
        proton_versions = [p for p in os.listdir(PROTON_PATH) if "Proton" in p]
        for version in proton_versions:
            proton_path = os.path.join(PROTON_PATH, version, 'dist/bin/wine')
            if os.path.isfile(proton_path):
                versions.append(version)
    return versions


def get_wine_version_exe(version):
    if not version:
        version = get_default_version()
    if not version:
        raise RuntimeError("Wine is not installed")
    return os.path.join(WINE_DIR, '{}/bin/wine'.format(version))


def is_version_installed(version):
    return os.path.isfile(get_wine_version_exe(version))


def is_esync_limit_set():
    """Checks if the number of files open is acceptable for esync usage."""
    if ESYNC_LIMIT_CHECK in ('0', 'off'):
        logger.info("fd limit check for esync was manually disabled")
        return True
    nolimit = subprocess.Popen("ulimit -Hn", shell=True, stdout=subprocess.PIPE).stdout.read()
    return int(nolimit) >= MIN_NUMBER_FILES_OPEN


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
    if version not in ('custom', 'system') and '-' not in version and 'Proton' not in version:
        logger.error("Legacy wine format used: %s", version)
        version += '-i386'
    return version


def is_version_esync(version, path):
    """Determines is a Wine build has both build and path, I have no fucking
    clue why both version and path are given to this function, seems redundant.

    Params:
        version: The Wine version name
        path: the path to the Wine version name (WHYYYYYYYY???????)


    Returns:
        bool: True is the build is Esync capable
    """
    version = version.lower()
    if 'esync' in version or 'proton' in version:
        return True

    command = path + " --version"
    wine_ver = str(subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout.read())
    return 'esync' in wine_ver.lower()


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


def display_vulkan_error(option, on_launch):
    if option == vulkan_available.NONE:
        message = "No Vulkan loader was detected."
    if option == vulkan_available.SIXTY_FOUR:
        message = "32-bit Vulkan loader was not detected."
    if option == vulkan_available.THIRTY_TWO:
        message = "64-bit Vulkan loader was not detected."

    if on_launch:
        checkbox_message = "Launch anyway and do not show this message again."
    else:
        checkbox_message = "Enable anyway and do not show this message again."

    setting = 'hide-no-vulkan-warning'
    DontShowAgainDialog(setting,
                        message,
                        secondary_message="Please follow the installation "
                        "procedures as described in\n"
                        "<a href='https://github.com/lutris/lutris/wiki/How-to:-DXVK'>"
                        "How-to:-DXVK (https://github.com/lutris/lutris/wiki/How-to:-DXVK)</a>",
                        checkbox_message=checkbox_message)
    return settings.read_setting(setting) == 'True'


def esync_display_limit_warning():
    ErrorDialog("Your limits are not set correctly."
                " Please increase them as described here:"
                " <a href='https://github.com/lutris/lutris/wiki/How-to:-Esync'>"
                "How-to:-Esync (https://github.com/lutris/lutris/wiki/How-to:-Esync)</a>")


def esync_display_version_warning(on_launch):
    setting = 'hide-wine-non-esync-version-warning'
    if on_launch:
        checkbox_message = "Launch anyway and do not show this message again."
    else:
        checkbox_message = "Enable anyway and do not show this message again."

    DontShowAgainDialog(setting,
                        "Incompatible Wine version detected",
                        secondary_message="The wine build you have selected "
                        "does not seem to support Esync.\n"
                        "Please switch to an esync-capable version.",
                        checkbox_message=checkbox_message)
    return settings.read_setting(setting) == 'True'


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
        ('d', []),
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
