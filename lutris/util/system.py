"""System utilities"""

import hashlib
import os
import re
import shutil
import signal
import stat
import string
import subprocess
import zipfile
from gettext import gettext as _
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gi.repository import Gio, GLib  # type: ignore

from lutris import settings
from lutris.exceptions import MissingExecutableError
from lutris.util.log import logger
from lutris.util.portals import TrashPortal

# Home folders that should never get deleted.
PROTECTED_HOME_FOLDERS = (
    _("Documents"),
    _("Downloads"),
    _("Desktop"),
    _("Pictures"),
    _("Videos"),
    _("Pictures"),
    _("Projects"),
    _("Games"),
)


def get_environment():
    """Return a safe to use copy of the system's environment.
    Values starting with BASH_FUNC can cause issues when written in a text file."""
    return {key: value for key, value in os.environ.items() if not key.startswith("BASH_FUNC")}


def execute(
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    quiet: bool = False,
    shell: bool = False,
    timeout: Optional[float] = None,
) -> str:
    """
    Execute a system command and return its standard output; standard error is discarded.

    Params:
        command (list): A list containing an executable and its parameters
        env (dict): Dict of values to add to the current environment
        cwd (str): Working directory
        quiet (bool): Do not display log messages
        timeout (int): Number of seconds the program is allowed to run, disabled by default

    Returns:
        str: stdout output
    """
    stdout, _stderr = _execute(command, env=env, cwd=cwd, quiet=quiet, shell=shell, timeout=timeout)
    return stdout


def execute_with_error(
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    quiet: bool = False,
    shell: bool = False,
    timeout: Optional[float] = None,
) -> Tuple[str, str]:
    """
    Execute a system command and return its standard output and; standard error in a tuple.

    Params:
        command (list): A list containing an executable and its parameters
        env (dict): Dict of values to add to the current environment
        cwd (str): Working directory
        quiet (bool): Do not display log messages
        timeout (int): Number of seconds the program is allowed to run, disabled by default

    Returns:
        str, str: stdout output and stderr output
    """
    return _execute(command, env=env, cwd=cwd, capture_stderr=True, quiet=quiet, shell=shell, timeout=timeout)


def _execute(
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    capture_stderr: bool = False,
    quiet: bool = False,
    shell: bool = False,
    timeout: Optional[float] = None,
) -> Tuple[str, str]:
    # Check if the executable exists
    if not command:
        logger.error("No executable provided!")
        return "", ""
    if os.path.isabs(command[0]) and not path_exists(command[0]):
        logger.error("No executable found in %s", command)
        return "", ""

    if not quiet:
        logger.debug("Executing %s", " ".join([str(i) for i in command]))

    # Set up environment
    existing_env = get_environment()
    if env:
        if not quiet:
            logger.debug(" ".join("{}={}".format(k, v) for k, v in env.items()))
        env = {k: v for k, v in env.items() if v is not None}
        existing_env.update(env)

    # Piping stderr can cause slowness in the programs, use carefully
    # (especially when using regedit with wine)
    try:
        with subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
            env=existing_env,
            cwd=cwd,
            errors="replace",
        ) as command_process:
            stdout, stderr = command_process.communicate(timeout=timeout)
    except (OSError, TypeError) as ex:
        logger.error("Could not run command %s (env: %s): %s", command, env, ex)
        return "", ""
    except subprocess.TimeoutExpired:
        logger.error("Command %s after %s seconds", command, timeout)
        return "", ""

    return stdout.strip(), (stderr or "").strip()


def spawn(command, env=None, cwd=None, quiet=False, shell=False):
    """
    Execute a system command but discard its results and do not wait
    for it to complete.

    Params:
        command (list): A list containing an executable and its parameters
        env (dict): Dict of values to add to the current environment
        cwd (str): Working directory
        quiet (bool): Do not display log messages
    """

    # Check if the executable exists
    if not command:
        logger.error("No executable provided!")
        return
    if os.path.isabs(command[0]) and not path_exists(command[0]):
        logger.error("No executable found in %s", command)
        return

    if not quiet:
        logger.debug("Spawning %s", " ".join([str(i) for i in command]))

    # Set up environment
    existing_env = get_environment()
    if env:
        if not quiet:
            logger.debug(" ".join("{}={}".format(k, v) for k, v in env.items()))
        env = {k: v for k, v in env.items() if v is not None}
        existing_env.update(env)

    # Piping stderr can cause slowness in the programs, use carefully
    # (especially when using regedit with wine)
    try:
        subprocess.Popen(  # pylint: disable=consider-using-with
            command, shell=shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=existing_env, cwd=cwd
        )
    except (OSError, TypeError) as ex:
        logger.error("Could not run command %s (env: %s): %s", command, env, ex)


def read_process_output(command, timeout=5, env=None, error_result=""):
    """Return the output of a command as a string; if 'error_result' is not None,
    returns that on errors. If it is, raises an exception instead."""
    try:
        return subprocess.check_output(command, timeout=timeout, env=env, encoding="utf-8", errors="ignore").strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
        logger.error("%s command failed: %s", command, ex)
        if error_result is None:
            raise
        return error_result


def get_md5_in_zip(filename):
    """Return the md5 hash of a file in a zip"""
    with zipfile.ZipFile(filename, "r") as archive:
        files = archive.namelist()
        if len(files) > 1:
            logger.warning("More than 1 file in archive %s, reading 1st one: %s", filename, files[0])
        with archive.open(files[0]) as file_in_zip:
            _hash = read_file_md5(file_in_zip)
    return _hash


def get_md5_hash(filename):
    """Return the md5 hash of a file."""
    try:
        with open(filename, "rb") as _file:
            _hash = read_file_md5(_file)
    except IOError:
        logger.warning("Error reading %s", filename)
        return False
    return _hash


def read_file_md5(filedesc):
    md5 = hashlib.md5()
    for chunk in iter(lambda: filedesc.read(8192), b""):
        md5.update(chunk)
    return md5.hexdigest()


def get_file_checksum(filename, hash_type):
    """Return the checksum of type `hash_type` for a given filename"""
    hasher = hashlib.new(hash_type)
    with open(filename, "rb") as input_file:
        for chunk in iter(lambda: input_file.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_executable(exec_path):
    """Return whether exec_path is an executable"""
    return os.access(exec_path, os.X_OK)


def make_executable(exec_path):
    file_stats = os.stat(exec_path)
    os.chmod(exec_path, file_stats.st_mode | stat.S_IEXEC)


def can_find_executable(exec_name: str) -> bool:
    """Checks if an executable can be located; if false,
    find_executable will return None, and find_required_executable
    will raise an exception."""
    return bool(find_executable(exec_name))


def find_executable(exec_name: str) -> Optional[str]:
    """Return the absolute path of an executable, or None if
    it could not be found."""
    return shutil.which(exec_name) if exec_name else None


def find_required_executable(exec_name: str) -> str:
    """Return the absolute path of an executable, but raises a
    MissingExecutableError if it could not be found."""
    exe = find_executable(exec_name)
    if not exe:
        raise MissingExecutableError(_("The executable '%s' could not be found.") % exec_name)
    return exe


def get_pid(program, multiple=False):
    """Return pid of process.

    :param str program: Name of the process.
    :param bool multiple: If True and multiple instances of the program exist,
        return all of them; if False only return the first one.
    """
    pids = execute(["pgrep", program])
    if not pids.strip():
        return
    pids = pids.split()
    if multiple:
        return pids
    return pids[0]


def kill_pid(pid):
    """Terminate a process referenced by its PID"""
    try:
        pid = int(pid)
    except ValueError:
        logger.error("Invalid pid %s")
        return
    logger.info("Killing PID %s", pid)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        logger.error("Could not kill process %s", pid)


def python_identifier(unsafe_string: str):
    """Converts a string to something that can be used as a python variable"""

    def _dashrepl(matchobj):
        return matchobj.group(0).replace("-", "_")

    return re.sub(r"(\${)([\w-]*)(})", _dashrepl, unsafe_string)


def substitute(string_template: str, variables):
    """Expand variables on a string template

    Args:
        string_template (str): template with variables preceded by $
        variables (dict): mapping of variable identifier > value

    Return:
        str: String with substituted values
    """
    string_template = python_identifier(str(string_template))
    identifiers = variables.keys()

    # We support dashes in identifiers but they are not valid in python
    # identifiers, which is a requirement for the templating engine we use
    # Replace the dashes with underscores in the mapping and template
    variables = dict((k.replace("-", "_"), v) for k, v in variables.items())
    for identifier in identifiers:
        string_template = string_template.replace("${}".format(identifier), "${}".format(identifier.replace("-", "_")))

    template = string.Template(string_template)
    if string_template in list(variables.keys()):
        return variables[string_template]
    return template.safe_substitute(variables)


def merge_folders(source, destination):
    """Merges the content of source to destination"""
    logger.debug("Merging %s into %s", source, destination)
    # We do not use shutil.copytree() here because that would copy
    # the file permissions, and we do not want them.
    source = os.path.abspath(source)
    for dirpath, dirnames, filenames in os.walk(source):
        source_relpath = dirpath[len(source) :].strip("/")
        dst_abspath = os.path.join(destination, source_relpath)
        for dirname in dirnames:
            new_dir = os.path.join(dst_abspath, dirname)
            logger.debug("creating dir: %s", new_dir)
            try:
                os.mkdir(new_dir)
            except OSError:
                pass
        for filename in filenames:
            # logger.debug("Copying %s", filename)
            if not os.path.exists(dst_abspath):
                os.makedirs(dst_abspath)
            shutil.copy(os.path.join(dirpath, filename), os.path.join(dst_abspath, filename), follow_symlinks=False)


def remove_folder(
    path: str,
    completion_function: Optional[TrashPortal.CompletionFunction] = None,
    error_function: Optional[TrashPortal.ErrorFunction] = None,
) -> None:
    """Trashes a folder specified by path, asynchronously. The folder
    likely exists after this returns, since it's using DBus to ask
    for the entrashification.
    """
    if not os.path.exists(path):
        logger.warning("Non existent path: %s", path)
        if completion_function:
            completion_function()
        return
    if os.path.samefile(os.path.expanduser("~"), path):
        if error_function:
            error_function(RuntimeError("Lutris tried to trash home directory!"))
        return

    logger.debug("Trashing folder %s", path)
    TrashPortal([path], completion_function=completion_function, error_function=error_function)


def delete_folder(path):
    """Delete a folder specified by path immediately. The folder will not
    be recoverable, so consider remove_folder() instead.

    Returns true if the folder was successfully deleted.
    """
    if not os.path.exists(path):
        logger.warning("Non existent path: %s", path)
        return False
    if os.path.samefile(os.path.expanduser("~"), path):
        raise RuntimeError("Lutris tried to erase home directory!")
    logger.debug("Deleting folder %s", path)
    try:
        shutil.rmtree(path)
    except OSError as ex:
        logger.error("Failed to delete folder %s: %s (Error code %s)", path, ex.strerror, ex.errno)
        return False
    return True


def create_folder(path):
    """Creates a folder specified by path"""
    if not path:
        return
    path = os.path.expanduser(path)
    os.makedirs(path, exist_ok=True)
    return path


def list_unique_folders(folders):
    """Deduplicate directories with the same Device.Inode"""
    unique_dirs = {}
    for folder in folders:
        folder_stat = os.stat(folder)
        identifier = "%s.%s" % (folder_stat.st_dev, folder_stat.st_ino)
        if identifier not in unique_dirs:
            unique_dirs[identifier] = folder
    return unique_dirs.values()


def is_removeable(path, system_config):
    """Check if a folder is safe to remove (not system or home, ...). This needs the
    system config dict so it can check the default game path, too."""
    if not path_exists(path):
        return False

    parts = path.strip("/").split("/")

    if not parts:
        return False

    if parts[0] == "var":
        # Fedora Silverblue puts mount points under /var since they are mutable
        # so we'll special case /var/mnt/<drive>/*.
        if len(parts) > 3 and parts[1] in ("mnt", "media"):
            return True
        return False

    if parts[0] in ("usr", "lib", "etc", "boot", "sbin", "bin"):
        # Path is part of the system folders
        return False

    if parts[0] == "home":
        if len(parts) <= 2:
            return False
        if len(parts) == 3 and parts[2] in PROTECTED_HOME_FOLDERS:
            return False

    if system_config:
        default_game_path = system_config.get("game_path")
        if path_contains(path, default_game_path, resolve_symlinks=False):
            return False

    return True


def fix_path_case(path):
    """Do a case-insensitive check, return the real path with correct case. If the path is
    not for a real file, this corrects as many components as do exist."""
    if not path or os.path.exists(path) or not path.startswith("/"):
        # If a path isn't provided, or it exists as is, or is a relative path, just return it.
        return path
    parts = path.strip("/").split("/")
    current_path = "/"
    for part in parts:
        parent_path = current_path
        current_path = os.path.join(current_path, part)
        if not os.path.exists(current_path) and os.path.isdir(parent_path):
            try:
                path_contents = os.listdir(parent_path)
            except OSError:
                logger.error("Can't read contents of %s", parent_path)
                path_contents = []
            for filename in path_contents:
                if filename.lower() == part.lower():
                    current_path = os.path.join(parent_path, filename)
                    break

    # Only return the path if we got the same number of elements
    if len(parts) == len(current_path.strip("/").split("/")):
        return current_path
    # otherwise return original path
    return path


def get_pids_using_file(path):
    """Return a set of pids using file `path`."""
    if not os.path.exists(path):
        logger.error("Can't return PIDs using non existing file: %s", path)
        return set()

    fuser_path = find_executable("fuser")
    if not fuser_path:
        logger.warning("fuser not available, please install psmisc")
        return set()
    fuser_output = execute([fuser_path, path], quiet=True)
    return set(fuser_output.split())


def reverse_expanduser(path):
    """Replace '/home/username' with '~' in given path."""
    if not path:
        return path
    user_path = os.path.expanduser("~")
    if path.startswith(user_path):
        path = path[len(user_path) :].strip("/")
        return "~/" + path
    return path


def path_contains(parent, child, resolve_symlinks=False) -> bool:
    """Tests if a child path is actually within a parent directory
    or a subdirectory of it. Resolves relative paths, and ~, and
    optionally symlinks."""

    if parent is None or child is None:
        return False

    resolved_parent = Path(os.path.abspath(os.path.expanduser(parent)))
    resolved_child = Path(os.path.abspath(os.path.expanduser(child)))

    if resolve_symlinks:
        resolved_parent = resolved_parent.resolve()
        resolved_child = resolved_child.resolve()

    return resolved_child == resolved_parent or resolved_parent in resolved_child.parents


def path_exists(path: str, check_symlinks: bool = False, exclude_empty: bool = False) -> bool:
    """Wrapper around system.path_exists that doesn't crash with empty values

    Params:
        path (str): File to the file to check
        check_symlinks (bool): If the path is a broken symlink, return False
        exclude_empty (bool): If true, consider 0 bytes files as non existing
    """
    if not path:
        return False
    if path.startswith("~"):
        path = os.path.expanduser(path)
    if os.path.exists(path):
        if exclude_empty:
            return os.stat(path).st_size > 0
        return True
    if os.path.islink(path):
        logger.warning("%s is a broken link", path)
        return not check_symlinks
    return False


def create_symlink(source: str, destination: str):
    """Create a symlink from source to destination.
    If there is already a symlink at the destination and it is broken, it will be deleted."""
    is_directory = os.path.isdir(source)
    if os.path.islink(destination) and not os.path.exists(destination):
        logger.warning("Deleting broken symlink %s", destination)
        os.remove(destination)
    try:
        os.symlink(source, destination, target_is_directory=is_directory)
    except OSError:
        logger.error("Failed linking %s to %s", source, destination)


def reset_library_preloads():
    """Remove library preloads from environment"""
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        if os.environ.get(key):
            try:
                del os.environ[key]
            except OSError:
                logger.error("Failed to delete environment variable %s", key)


def get_existing_parent(path):
    """Return the 1st existing parent for a folder (or itself if the path
    exists and is a directory). returns None, when none of the parents exists.
    """
    if path == "":
        return None
    if os.path.exists(path) and not os.path.isfile(path):
        return path
    return get_existing_parent(os.path.dirname(path))


def update_desktop_icons():
    """Update Icon for GTK+ desktop manager
    Other desktop manager icon cache commands must be added here if needed
    """
    if can_find_executable("gtk-update-icon-cache"):
        execute(["gtk-update-icon-cache", "-tf", os.path.join(GLib.get_user_data_dir(), "icons/hicolor")], quiet=True)
        execute(["gtk-update-icon-cache", "-tf", os.path.join(settings.RUNTIME_DIR, "icons/hicolor")], quiet=True)


def get_disk_size(path: str) -> int:
    """Return the disk size in bytes of a file or folder"""

    def get_file_size(file_path):
        return os.stat(file_path).st_size

    if os.path.isfile(path):
        return get_file_size(path)

    total_size = 0
    for base, _dirs, files in os.walk(path):
        paths = [os.path.join(base, f) for f in files]
        total_size += sum(get_file_size(p) for p in paths if os.path.isfile(p) and not os.path.islink(p))
    return total_size


def get_locale_list():
    """Return list of available locales"""
    try:
        with subprocess.Popen(["locale", "-a"], stdout=subprocess.PIPE) as locale_getter:
            output = locale_getter.communicate()
        locales = output[0].decode("ASCII").split()  # locale names use only ascii characters
    except FileNotFoundError:
        lang = os.environ.get("LANG", "")
        if lang:
            locales = [lang]
        else:
            locales = []
    return locales


def get_running_pid_list():
    """Return the list of PIDs from processes currently running"""
    return [int(p) for p in os.listdir("/proc") if p[0].isdigit()]


def get_mounted_discs():
    """Return a list of mounted discs and ISOs

    :rtype: list of Gio.Mount
    """
    volumes = Gio.VolumeMonitor.get()
    drives = []

    for mount in volumes.get_mounts():
        if mount.get_volume():
            device = mount.get_volume().get_identifier("unix-device")
            if not device:
                logger.debug("No device for mount %s", mount.get_name())
                continue

            # Device is a disk drive or ISO image
            if "/dev/sr" in device or "/dev/loop" in device:
                drives.append(mount.get_root().get_path())
    return drives


def find_mount_point(path):
    """Return the mount point a file is located on"""
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path


def set_keyboard_layout(layout):
    setxkbmap_command = ["setxkbmap", "-model", "pc101", layout, "-print"]
    xkbcomp_command = ["xkbcomp", "-", os.environ.get("DISPLAY", ":0")]
    with subprocess.Popen(xkbcomp_command, stdin=subprocess.PIPE) as xkbcomp:
        with subprocess.Popen(setxkbmap_command, env=os.environ, stdout=xkbcomp.stdin) as setxkbmap:
            setxkbmap.communicate()
            xkbcomp.communicate()
