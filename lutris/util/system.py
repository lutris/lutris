"""System utilities"""
import hashlib
import signal
import os
import re
import shutil
import string
import subprocess

from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger


def execute(command, env=None, cwd=None, log_errors=False, quiet=False, shell=False):
    """
        Execute a system command and return its results.

        Params:
            command (list): A list containing an executable and its parameters
            env (dict): Dict of values to add to the current environment
            cwd (str): Working directory
            log_errors (bool): Pipe stderr to stdout (might cause slowdowns)
            quiet (bool): Do not display log messages

        Returns:
            str: stdout output
    """

    # Check if the executable exists
    if not command:
        logger.error("No executable provided!")
        return
    if os.path.isabs(command[0]) and not path_exists(command[0]):
        logger.error("No executable found in %s", command)
        return

    if not quiet:
        logger.debug("Executing %s", " ".join(command))

    # Set up environment
    existing_env = os.environ.copy()
    if env:
        if not quiet:
            logger.debug(" ".join("{}={}".format(k, v) for k, v in env.items()))
        env = {k: v for k, v in env.items() if v is not None}
        existing_env.update(env)

    # Piping stderr can cause slowness in the programs, use carefully
    # (especially when using regedit with wine)
    try:
        stdout, stderr = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if log_errors else subprocess.DEVNULL,
            env=existing_env,
            cwd=cwd,
        ).communicate()
    except (OSError, TypeError) as ex:
        logger.error("Could not run command %s (env: %s): %s", command, env, ex)
        return
    if stderr and log_errors:
        logger.error(stderr)
    return stdout.decode(errors="replace").strip()


def get_md5_hash(filename):
    """Return the md5 hash of a file."""
    md5 = hashlib.md5()
    try:
        with open(filename, "rb") as _file:
            for chunk in iter(lambda: _file.read(8192), b""):
                md5.update(chunk)
    except IOError:
        print("Error reading %s" % filename)
        return False
    return md5.hexdigest()


def get_file_checksum(filename, hash_type):
    """Return the checksum of type `hash_type` for a given filename"""
    hasher = hashlib.new(hash_type)
    with open(filename, "rb") as input_file:
        for chunk in iter(lambda: input_file.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_executable(exec_name):
    """Return the absolute path of an executable"""
    if not exec_name:
        return None
    cached = LINUX_SYSTEM.get(exec_name)
    if cached:
        return cached
    return shutil.which(exec_name)


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


def python_identifier(unsafe_string):
    """Converts a string to something that can be used as a python variable"""
    if not isinstance(unsafe_string, str):
        logger.error("Cannot convert %s to a python identifier", type(unsafe_string))
        return

    def _dashrepl(matchobj):
        return matchobj.group(0).replace("-", "_")

    return re.sub(r"(\${)([\w-]*)(})", _dashrepl, unsafe_string)


def substitute(string_template, variables):
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
    # identifers, which is a requirement for the templating engine we use
    # Replace the dashes with underscores in the mapping and template
    variables = dict((k.replace("-", "_"), v) for k, v in variables.items())
    for identifier in identifiers:
        string_template = string_template.replace(
            "${}".format(identifier), "${}".format(identifier.replace("-", "_"))
        )

    template = string.Template(string_template)
    if string_template in list(variables.keys()):
        return variables[string_template]
    return template.safe_substitute(variables)


def merge_folders(source, destination):
    """Merges the content of source to destination"""
    logger.debug("Merging %s into %s", source, destination)
    source = os.path.abspath(source)
    for (dirpath, dirnames, filenames) in os.walk(source):
        source_relpath = dirpath[len(source):].strip("/")
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
            shutil.copy(
                os.path.join(dirpath, filename), os.path.join(dst_abspath, filename)
            )


def remove_folder(path):
    """Delete a folder specified by path"""
    if not os.path.exists(path):
        logger.warning("Non existent path: %s", path)
        return
    logger.debug("Removing folder %s", path)
    if os.path.samefile(os.path.expanduser("~"), path):
        raise RuntimeError("Lutris tried to erase home directory!")
    shutil.rmtree(path)


def create_folder(path):
    """Creates a folder specified by path"""
    if not path:
        return
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def is_removeable(path, excludes=None):
    """Check if a folder is safe to remove (not system or home, ...)"""
    if not path_exists(path) or path in excludes:
        return False

    parts = path.strip("/").split("/")
    if parts[0] in ("usr", "var", "lib", "etc", "boot", "sbin", "bin"):
        # Path is part of the system folders
        return False

    if parts[0] == "home":
        if len(parts) <= 2:
            # Path is a home folder
            return False
        if parts[2] == ".wine":
            # Protect main .wine folder
            return False

    return True


def fix_path_case(path):
    """Do a case insensitive check, return the real path with correct case."""
    if os.path.exists(path):
        return path
    parts = path.strip("/").split("/")
    current_path = "/"
    for part in parts:
        if not os.path.exists(current_path):
            return
        tested_path = os.path.join(current_path, part)
        if os.path.exists(tested_path):
            current_path = tested_path
            continue
        try:
            path_contents = os.listdir(current_path)
        except OSError:
            logger.error("Can't read contents of %s", current_path)
            path_contents = []
        for filename in path_contents:
            if filename.lower() == part.lower():
                current_path = os.path.join(current_path, filename)
                continue

    # Only return the path if we got the same number of elements
    if len(parts) == len(current_path.strip("/").split("/")):
        return current_path


def get_pids_using_file(path):
    """Return a set of pids using file `path`."""
    if not os.path.exists(path):
        logger.error("Can't return PIDs using non existing file: %s", path)
        return set()
    fuser_path = find_executable("fuser")
    if not fuser_path:
        logger.warning("fuser not available, please install psmisc")
        return set([])
    fuser_output = execute([fuser_path, path], quiet=True)
    return set(fuser_output.split())


def get_terminal_apps():
    """Return the list of installed terminal emulators"""
    return LINUX_SYSTEM.get_terminals()


def get_default_terminal():
    """Return the default terminal emulator"""
    terms = get_terminal_apps()
    if terms:
        return terms[0]
    logger.error("Couldn't find a terminal emulator.")


def reverse_expanduser(path):
    """Replace '/home/username' with '~' in given path."""
    if not path:
        return path
    user_path = os.path.expanduser("~")
    if path.startswith(user_path):
        path = path[len(user_path):].strip("/")
        return "~/" + path
    return path


def path_exists(path, check_symlinks=False):
    """Wrapper around system.path_exists that doesn't crash with empty values

    Params:
        path (str): File to the file to check
        check_symlinks (bool): If the path is a broken symlink, return False
    """
    if not path:
        return False
    if os.path.exists(path):
        return True
    if os.path.islink(path):
        logger.warning("%s is a broken link", path)
        return not check_symlinks
    return False


def reset_library_preloads():
    """Remove library preloads from environment"""
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        if os.environ.get(key):
            del os.environ[key]


def run_once(function):
    """Decorator to use on functions intended to run only once"""
    first_run = True

    def fn_wrapper(*args):
        nonlocal first_run
        if first_run:
            first_run = False
            return function(*args)
    return fn_wrapper
