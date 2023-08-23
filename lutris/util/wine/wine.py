"""Utilities for manipulating Wine"""
import os
from collections import OrderedDict
from functools import lru_cache
from gettext import gettext as _

from lutris import runtime, settings
from lutris.api import get_default_runner_version
from lutris.exceptions import UnavailableRunnerError
from lutris.gui.dialogs import ErrorDialog, WarningMessageDialog
from lutris.util import linux, system
from lutris.util.log import logger
from lutris.util.steam.config import get_steamapps_dirs
from lutris.util.strings import parse_version
from lutris.util.wine import fsync

WINE_DIR = os.path.join(settings.RUNNER_DIR, "wine")
WINE_DEFAULT_ARCH = "win64" if linux.LINUX_SYSTEM.is_64_bit else "win32"
WINE_PATHS = {
    "winehq-devel": "/opt/wine-devel/bin/wine",
    "winehq-staging": "/opt/wine-staging/bin/wine",
    "wine-development": "/usr/lib/wine-development/wine",
    "system": "wine",
}

# Insert additional system-wide Wine installations, such as are found
# on Gentoo.
try:
    for _candidate in os.listdir('/usr/lib/'):
        if _candidate.startswith("wine-"):
            _wine_path = os.path.join("/usr/lib/", _candidate, "bin/wine")
            if os.path.isfile(_wine_path):
                WINE_PATHS["System " + _candidate] = _wine_path
    _candidate = None
    _wine_path = None
except Exception as ex:
    logger.exception("Unable to enumerate system Wine versions: %s", ex)


def _iter_proton_locations():
    """Iterate through all existing Proton locations"""
    try:
        steamapp_dirs = get_steamapps_dirs()
    except:
        return  # in case of corrupt or unreadable Steam configuration files!

    for path in [os.path.join(p, "common") for p in steamapp_dirs]:
        if os.path.isdir(path):
            yield path
    for path in [os.path.join(p, "") for p in steamapp_dirs]:
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
            if system.path_exists(os.path.join(path, version, "files/bin/wine")):
                paths.add(path)
    return list(paths)


def detect_arch(prefix_path=None, wine_path=None):
    """Given a Wine prefix path, return its architecture"""
    if prefix_path:
        arch = detect_prefix_arch(prefix_path)
        if arch:
            return arch
    if wine_path and system.path_exists(wine_path + "64"):
        return "win64"
    return "win32"


def detect_prefix_arch(prefix_path):
    """Return the architecture of the prefix found in `prefix_path`"""
    if not prefix_path:
        raise RuntimeError("The prefix architecture can't be detected with no prefix path.")

    prefix_path = os.path.expanduser(prefix_path)
    registry_path = os.path.join(prefix_path, "system.reg")
    if not os.path.isdir(prefix_path) or not os.path.isfile(registry_path):
        # No prefix_path exists or invalid prefix
        logger.error("Prefix not found: %s", prefix_path)
        return None
    with open(registry_path, "r", encoding='utf-8') as registry:
        for _line_no in range(5):
            line = registry.readline()
            if "win64" in line:
                return "win64"
            if "win32" in line:
                return "win32"
    logger.error("Failed to detect Wine prefix architecture in %s", prefix_path)
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
    The runtime can be forced to be disabled, otherwise
    it's disabled automatically if Wine is installed system wide.
    """
    if force_disable or runtime.RUNTIME_DISABLED:
        return False
    if WINE_DIR in wine_path:
        return True
    if is_installed_systemwide():
        return False
    return True


def is_gstreamer_build(wine_path):
    """Returns whether a wine build ships with gstreamer libraries.
    This allows to set GST_PLUGIN_SYSTEM_PATH_1_0 for the builds that support it.
    """
    base_path = os.path.dirname(os.path.dirname(wine_path))
    return system.path_exists(os.path.join(base_path, "lib64/gstreamer-1.0"))


def is_installed_systemwide():
    """Return whether Wine is installed outside of Lutris"""
    for build in WINE_PATHS.values():
        if system.find_executable(build):
            return True
    return False


def list_system_wine_versions():
    """Return the list of wine versions installed on the system"""
    return [
        build
        for build, path in WINE_PATHS.items()
        if get_system_wine_version(path)
    ]


def get_lutris_wine_versions():
    """Return the list of wine versions installed by lutris"""
    if not system.path_exists(WINE_DIR):
        return []
    versions = []
    for dirname in version_sort(os.listdir(WINE_DIR), reverse=True):
        try:
            if os.path.isfile(get_wine_version_exe(dirname)):
                versions.append(dirname)
        except UnavailableRunnerError:
            pass  # if it's not properly installed, skip it
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
            # Support Proton Experimental
            path = os.path.join(proton_path, version, "files/bin/wine")
            if os.path.isfile(path):
                versions.append(version)
    return versions


@lru_cache(maxsize=8)
def get_wine_versions():
    """Return the list of Wine versions installed"""
    return list_system_wine_versions() + get_lutris_wine_versions() + get_proton_versions()


def get_wine_version_exe(version):
    if not version:
        version = get_default_version()
    if not version:
        raise UnavailableRunnerError(_("Wine is not installed"))
    if version in WINE_PATHS:
        return WINE_PATHS[version]
    return os.path.join(WINE_DIR, "{}/bin/wine".format(version))


def parse_wine_version(version):
    """This is a specialized parse_version() that adjusts some odd
    Wine versions for correct parsing."""
    version = version.replace("Proton7-", "Proton-7.")
    version = version.replace("Proton8-", "Proton-8.")
    return parse_version(version)


def version_sort(versions, reverse=False):
    def version_key(version):
        version_list, prefix, suffix = parse_wine_version(version)
        # Normalize the length of sub-versions
        sort_key = version_list + [0] * (10 - len(version_list))
        sort_key.append(prefix)
        sort_key.append(suffix)
        return sort_key

    return sorted(versions, key=version_key, reverse=reverse)


def is_esync_limit_set():
    """Checks if the number of files open is acceptable for esync usage."""
    return linux.LINUX_SYSTEM.has_enough_file_descriptors()


def is_fsync_supported():
    """Checks if the running kernel has Valve's futex patch applied."""
    return fsync.get_fsync_support()


def get_default_version():
    """Return the default version of wine."""
    installed_versions = get_wine_versions()
    if installed_versions:
        default_version = get_default_runner_version("wine")
        if default_version:
            vers = default_version["version"] + '-' + default_version["architecture"]
            if vers in installed_versions:
                return vers
        return installed_versions[0]
    return None


def get_system_wine_version(wine_path="wine"):
    """Return the version of Wine installed on the system."""
    if wine_path != "wine" and not system.path_exists(wine_path):
        return ""
    if wine_path == "wine" and not system.find_executable("wine"):
        return ""
    version = system.read_process_output([wine_path, "--version"])
    if not version:
        logger.error("Error reading wine version for %s", wine_path)
        return ""
    if version.startswith("wine-"):
        version = version[5:]
    return version


def is_version_esync(path):
    """Determines if a Wine build is Esync capable"""
    compat_versions = ["esync", "lutris", "tkg", "ge", "proton", "staging"]
    try:
        version = path.split("/")[-3].lower()
    except IndexError:
        logger.error("Invalid path '%s'", path)
        return False
    for is_esync in compat_versions:
        if is_esync in version:
            return True
    system_version = get_system_wine_version(path)
    if system_version:
        system_version = system_version.lower()
        for is_esync in compat_versions:
            if is_esync in system_version:
                return True
    return False


def is_version_fsync(path):
    """Determines if a Wine build is Fsync capable"""
    compat_versions = ["fsync", "lutris", "tkg", "ge", "proton"]
    try:
        version = path.split("/")[-3].lower()
    except IndexError:
        logger.error("Invalid path '%s'", path)
        return False
    for fsync_version in compat_versions:
        if fsync_version in version:
            return True
    system_version = get_system_wine_version(path)
    if system_version:
        system_version = system_version.lower()
        for is_esync in compat_versions:
            if is_esync in system_version:
                return True
        return "fsync" in system_version.lower()
    return False


def get_real_executable(windows_executable, working_dir=None):
    """Given a Windows executable, return the real program
    capable of launching it along with necessary arguments."""

    exec_name = windows_executable.lower()

    if exec_name.endswith(".msi"):
        return ("msiexec", ["/i", windows_executable], working_dir)

    if exec_name.endswith(".bat"):
        if not working_dir or os.path.dirname(windows_executable) == working_dir:
            working_dir = os.path.dirname(windows_executable)
            windows_executable = os.path.basename(windows_executable)
        return ("cmd", ["/C", windows_executable], working_dir)

    if exec_name.endswith(".lnk"):
        return ("start", ["/unix", windows_executable], working_dir)

    return (windows_executable, [], working_dir)


def esync_display_limit_warning(parent=None):
    ErrorDialog(_(
        "Your limits are not set correctly."
        " Please increase them as described here:"
        " <a href='https://github.com/lutris/docs/blob/master/HowToEsync.md'>"
        "How-to:-Esync (https://github.com/lutris/docs/blob/master/HowToEsync.md)</a>"
    ), parent=parent)


def fsync_display_support_warning(parent=None):
    ErrorDialog(_(
        "Your kernel is not patched for fsync."
        " Please get a patched kernel to use fsync."
    ), parent=parent)


def esync_display_version_warning(parent=None):
    WarningMessageDialog(
        _("Incompatible Wine version detected"),
        secondary_message=_(
            "The Wine build you have selected "
            "does not support Esync.\n"
            "Please switch to an Esync-capable version."
        ),
        parent=parent
    )


def fsync_display_version_warning(parent=None):
    WarningMessageDialog(
        _("Incompatible Wine version detected"),
        secondary_message=_(
            "The Wine build you have selected "
            "does not support Fsync.\n"
            "Please switch to an Fsync-capable version."
        ),
        parent=parent
    )


def get_overrides_env(overrides):
    """
    Output a string of dll overrides usable with WINEDLLOVERRIDES
    See: https://wiki.winehq.org/Wine_User%27s_Guide#WINEDLLOVERRIDES.3DDLL_Overrides
    """
    default_overrides = {
        "winemenubuilder": ""
    }
    overrides.update(default_overrides)
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
