"""Utilities for manipulating Wine"""
# Standard Library
import os
import subprocess
from collections import OrderedDict
from functools import lru_cache
from gettext import gettext as _

# Lutris Modules
from lutris import runtime, settings
from lutris.gui.dialogs import DontShowAgainDialog, ErrorDialog
from lutris.runners.steam import steam
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import parse_version, version_sort
from lutris.util.wine import fsync

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
WINE_DEFAULT_ARCH = "win64" if system.LINUX_SYSTEM.is_64_bit else "win32"
WINE_PATHS = {
    "winehq-devel": "/opt/wine-devel/bin/wine",
    "winehq-staging": "/opt/wine-staging/bin/wine",
    "wine-development": "/usr/lib/wine-development/wine",
    "system": "wine",
}

ESYNC_LIMIT_CHECK = os.environ.get("ESYNC_LIMIT_CHECK", "").lower()
FSYNC_SUPPORT_CHECK = os.environ.get("FSYNC_SUPPORT_CHECK", "").lower()


def get_playonlinux():
    """Return the folder containing PoL config files"""
    pol_path = os.path.expanduser("~/.PlayOnLinux")
    if system.path_exists(os.path.join(pol_path, "wine")):
        return pol_path
    return None


def _iter_proton_locations():
    """Iterate through all existing Proton locations"""
    for path in [os.path.join(p, "common") for p in steam().get_steamapps_dirs()]:
        if os.path.isdir(path):
            yield path
    for path in [os.path.join(p, "") for p in steam().get_steamapps_dirs()]:
        if os.path.isdir(path):
            yield path


def get_proton_paths():
    """Get the Folder that contains all the Proton versions. Can probably be improved"""
    paths = set()
    for path in _iter_proton_locations():
        proton_versions = [p for p in os.listdir(path) if "Proton" in p]
        for version in proton_versions:
            if system.path_exists(os.path.join(path, version, "dist/bin/wine")):
                paths.add(path)
    return list(paths)


POL_PATH = get_playonlinux()


def detect_arch(prefix_path=None, wine_path=None):
    """Given a Wine prefix path, return its architecture"""
    arch = detect_prefix_arch(prefix_path)
    if arch:
        return arch
    if wine_path and system.path_exists(wine_path + "64"):
        return "win64"
    return "win32"


def detect_prefix_arch(prefix_path=None):
    """Return the architecture of the prefix found in `prefix_path`.

    If no `prefix_path` given, return the arch of the system's default prefix.
    If no prefix found, return None."""
    if not prefix_path:
        prefix_path = "~/.wine"
    prefix_path = os.path.expanduser(prefix_path)
    registry_path = os.path.join(prefix_path, "system.reg")
    if not os.path.isdir(prefix_path) or not os.path.isfile(registry_path):
        # No prefix_path exists or invalid prefix
        logger.debug("Prefix not found: %s", prefix_path)
        return None
    with open(registry_path, "r") as registry:
        for _line_no in range(5):
            line = registry.readline()
            if "win64" in line:
                return "win64"
            if "win32" in line:
                return "win32"
    logger.debug("Failed to detect Wine prefix architecture in %s", prefix_path)
    return None


def set_drive_path(prefix, letter, path):
    """Changes the path to a Wine drive"""
    dosdevices_path = os.path.join(prefix, "dosdevices")
    if not system.path_exists(dosdevices_path):
        raise OSError("Invalid prefix path %s" % prefix)
    drive_path = os.path.join(dosdevices_path, letter + ":")
    if system.path_exists(drive_path):
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
        logger.debug("%s is provided by Lutris, using runtime", wine_path)
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
            # if wine64 is installed but not wine32, don't consider it
            # a system-wide installation.
            if (
                build == "wine" and system.path_exists("/usr/lib/wine/wine64")
                and not system.path_exists("/usr/lib/wine/wine")
            ):
                logger.warning("wine32 is missing from system")
                return False
            return True
    return False


def get_system_wine_versions():
    """Return the list of wine versions installed on the system"""
    versions = []
    for build in sorted(WINE_PATHS.keys()):
        version = get_system_wine_version(WINE_PATHS[build])
        if version:
            versions.append(build)
    return versions


def get_lutris_wine_versions():
    """Return the list of wine versions installed by lutris"""
    versions = []
    if system.path_exists(WINE_DIR):
        dirs = version_sort(os.listdir(WINE_DIR), reverse=True)
        for dirname in dirs:
            if is_version_installed(dirname):
                versions.append(dirname)
    return versions


def get_proton_versions():
    """Return the list of Proton versions installed in Steam"""
    versions = []
    for proton_path in get_proton_paths():
        proton_versions = [p for p in os.listdir(proton_path) if "Proton" in p]
        for version in proton_versions:
            path = os.path.join(proton_path, version, "dist/bin/wine")
            if os.path.isfile(path):
                versions.append(version)
    return versions


def get_pol_wine_versions():
    """Return the list of wine versions installed by Play on Linux"""
    if not POL_PATH:
        return []
    versions = []
    for arch in ['x86', 'amd64']:
        builds_path = os.path.join(POL_PATH, "wine/linux-%s" % arch)
        if not system.path_exists(builds_path):
            continue
        for version in os.listdir(builds_path):
            if system.path_exists(os.path.join(builds_path, version, "bin/wine")):
                versions.append("PlayOnLinux %s-%s" % (version, arch))
    return versions


@lru_cache(maxsize=8)
def get_wine_versions():
    """Return the list of Wine versions installed"""
    versions = []
    versions += get_system_wine_versions()
    versions += get_lutris_wine_versions()
    versions += get_proton_versions()
    versions += get_pol_wine_versions()
    return versions


def get_wine_version_exe(version):
    if not version:
        version = get_default_version()
    if not version:
        raise RuntimeError("Wine is not installed")
    return os.path.join(WINE_DIR, "{}/bin/wine".format(version))


def is_version_installed(version):
    return os.path.isfile(get_wine_version_exe(version))


def is_esync_limit_set():
    """Checks if the number of files open is acceptable for esync usage."""
    if ESYNC_LIMIT_CHECK in ("0", "off"):
        logger.info("fd limit check for esync was manually disabled")
        return True
    return system.LINUX_SYSTEM.has_enough_file_descriptors()


def is_fsync_supported():
    """Checks if the running kernel has Valve's futex patch applied."""
    if FSYNC_SUPPORT_CHECK in ("0", "off"):
        logger.info("futex patch check for fsync was manually disabled")
        return True
    return fsync.is_fsync_supported()


def get_default_version():
    """Return the default version of wine. Prioritize 64bit builds"""
    installed_versions = get_wine_versions()
    wine64_versions = [version for version in installed_versions if "64" in version]
    if wine64_versions:
        return wine64_versions[0]
    if installed_versions:
        return installed_versions[0]
    return


def get_system_wine_version(wine_path="wine"):
    """Return the version of Wine installed on the system."""
    if wine_path != "wine" and not system.path_exists(wine_path):
        return
    if wine_path == "wine" and not system.find_executable("wine"):
        return
    if os.path.isabs(wine_path):
        wine_stats = os.stat(wine_path)
        if wine_stats.st_size < 2000:
            # This version is a script, ignore it
            return
    try:
        version = subprocess.check_output([wine_path, "--version"]).decode().strip()
    except (OSError, subprocess.CalledProcessError) as ex:
        logger.exception("Error reading wine version for %s: %s", wine_path, ex)
        return
    else:
        if version.startswith("wine-"):
            version = version[5:]
        return version
    return


def is_version_esync(path):
    """Determines if a Wine build is Esync capable

    Params:
        path: the path to the Wine version

    Returns:
        bool: True is the build is Esync capable
    """
    try:
        version = path.split("/")[-3].lower()
    except IndexError:
        logger.error("Invalid path '%s'", path)
        return False
    version_number, version_prefix, version_suffix = parse_version(version)
    esync_compatible_versions = ["esync", "lutris", "tkg", "ge", "proton"]
    for esync_version in esync_compatible_versions:
        if esync_version in version_prefix or esync_version in version_suffix:
            return True

    wine_ver = str(subprocess.check_output([path, "--version"])).lower()
    version, *_ = wine_ver.split()
    version_number, version_prefix, version_suffix = parse_version(version)

    if "esync" in wine_ver:
        return True
    if "staging" in wine_ver and version_number[0] >= 4 and version_number[1] >= 6:
        # Support for esync was merged in Wine Staging 4.6
        return True
    return False


def is_version_fsync(path):
    """Determines if a Wine build is Fsync capable

    Params:
        path: the path to the Wine version

    Returns:
        bool: True is the build is Fsync capable
    """
    try:
        version = path.split("/")[-3].lower()
    except IndexError:
        logger.error("Invalid path '%s'", path)
        return False
    _, version_prefix, version_suffix = parse_version(version)
    fsync_compatible_versions = ["fsync", "lutris", "ge", "proton"]
    for fsync_version in fsync_compatible_versions:
        if fsync_version in version_prefix or fsync_version in version_suffix:
            return True

    wine_ver = str(subprocess.check_output([path, "--version"])).lower()
    if "fsync" in wine_ver:
        return True
    return False


def get_real_executable(windows_executable, working_dir=None):
    """Given a Windows executable, return the real program
    capable of launching it along with necessary arguments."""

    exec_name = windows_executable.lower()

    if exec_name.endswith(".msi"):
        return ("msiexec", ["/i", windows_executable], working_dir)

    if exec_name.endswith(".bat"):
        if not working_dir or os.path.dirname(windows_executable) == working_dir:
            working_dir = os.path.dirname(windows_executable) or None
            windows_executable = os.path.basename(windows_executable)
        return ("cmd", ["/C", windows_executable], working_dir)

    if exec_name.endswith(".lnk"):
        return ("start", ["/unix", windows_executable], working_dir)

    return (windows_executable, [], working_dir)


def display_vulkan_error(on_launch):
    if on_launch:
        checkbox_message = "Launch anyway and do not show this message again."
    else:
        checkbox_message = "Enable anyway and do not show this message again."

    setting = "hide-no-vulkan-warning"
    DontShowAgainDialog(
        setting,
        "Vulkan is not installed or is not supported by your system",
        secondary_message="If you have compatible hardware, please follow "
        "the installation procedures as described in\n"
        "<a href='https://github.com/lutris/lutris/wiki/How-to:-DXVK'>"
        "How-to:-DXVK (https://github.com/lutris/lutris/wiki/How-to:-DXVK)</a>",
        checkbox_message=checkbox_message,
    )
    return settings.read_setting(setting) == "True"


def esync_display_limit_warning():
    ErrorDialog(
        "Your limits are not set correctly."
        " Please increase them as described here:"
        " <a href='https://github.com/lutris/lutris/wiki/How-to:-Esync'>"
        "How-to:-Esync (https://github.com/lutris/lutris/wiki/How-to:-Esync)</a>"
    )


def fsync_display_support_warning():
    ErrorDialog(_(
        "Your kernel is not patched for fsync."
        " Please get a patched kernel to use fsync."
    ))


def esync_display_version_warning(on_launch=False):
    setting = "hide-wine-non-esync-version-warning"
    if on_launch:
        checkbox_message = "Launch anyway and do not show this message again."
    else:
        checkbox_message = "Enable anyway and do not show this message again."

    DontShowAgainDialog(
        setting,
        "Incompatible Wine version detected",
        secondary_message="The Wine build you have selected "
        "does not support Esync.\n"
        "Please switch to an esync-capable version.",
        checkbox_message=checkbox_message,
    )
    return settings.read_setting(setting) == "True"


def fsync_display_version_warning(on_launch=False):
    setting = "hide-wine-non-fsync-version-warning"
    if on_launch:
        checkbox_message = "Launch anyway and do not show this message again."
    else:
        checkbox_message = "Enable anyway and do not show this message again."

    DontShowAgainDialog(
        setting,
        "Incompatible Wine version detected",
        secondary_message="The Wine build you have selected "
        "does not support Fsync.\n"
        "Please switch to an fsync-capable version.",
        checkbox_message=checkbox_message,
    )
    return settings.read_setting(setting) == "True"


def get_overrides_env(overrides):
    """
    Output a string of dll overrides usable with WINEDLLOVERRIDES
    See: https://wiki.winehq.org/Wine_User%27s_Guide#WINEDLLOVERRIDES.3DDLL_Overrides
    """
    if not overrides:
        return ""
    override_buckets = OrderedDict([("n,b", []), ("b,n", []), ("b", []), ("n", []), ("d", []), ("", [])])
    for dll, value in overrides.items():
        if not value:
            value = ""
        value = value.replace(" ", "")
        value = value.replace("builtin", "b")
        value = value.replace("native", "n")
        value = value.replace("disabled", "")
        try:
            override_buckets[value].append(dll)
        except KeyError:
            logger.error("Invalid override value %s", value)
            continue

    override_strings = []
    for value, dlls in override_buckets.items():
        if not dlls:
            continue
        override_strings.append("{}={}".format(",".join(sorted(dlls)), value))
    return ";".join(override_strings)
