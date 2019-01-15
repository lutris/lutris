"""System utilities"""
# pylint: disable=inconsistent-return-statements
import platform
import resource
import hashlib
import signal
import os
import re
import shutil
import string
import subprocess
import sys
import traceback
from collections import defaultdict

from lutris.util import drivers
from lutris.util.log import logger

SYSTEM_COMPONENTS = {
    "COMMANDS": [
        "xrandr",
        "fuser",
        "glxinfo",
        "vulkaninfo",
        "optirun",
        "primusrun",
        "xboxdrv",
        "pulseaudio",
        "lsi-steam",
        "fuser",
        "7z",
        "gtk-update-icon-cache",
        "lspci",
        "xgamma",
        "ldconfig",
        "strangle",
        "Xephyr",
        "nvidia-smi",
        "wine",
        "fluidsynth",
    ],
    "TERMINALS": [
        "xterm",
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "pantheon-terminal",
        "terminator",
        "mate-terminal",
        "urxvt",
        "cool-retro-term",
        "Eterm",
        "guake",
        "lilyterm",
        "lxterminal",
        "roxterm",
        "rxvt",
        "aterm",
        "sakura",
        "st",
        "terminology",
        "termite",
        "tilix",
        "wterm",
        "kitty",
        "yuakuake",
    ],
    "LIBRARIES": {
        "OPENGL": [
            "libGL.so.1",
        ],
        "VULKAN": [
            "libvulkan.so.1",
        ],
        "WINE": [
            "libsqlite3.so.0"
        ],
        "RADEON": [
            "libvulkan_radeon.so"
        ],
        "GAMEMODE": [
            "libgamemodeauto.so"
        ]
    }
}


class LinuxSystem:
    """Global cache for system commands"""
    _cache = {}

    lib_folders = [
        ('/lib', '/lib64'),
        ('/lib32', '/lib64'),
        ('/usr/lib', '/usr/lib64'),
        ('/usr/lib32', '/usr/lib64'),
        ('/lib/i386-linux-gnu', '/lib/x86_64-linux-gnu'),
        ('/usr/lib/i386-linux-gnu', '/usr/lib/x86_64-linux-gnu'),
    ]
    soundfont_folders = [
        '/usr/share/sounds/sf2',
        '/usr/share/soundfonts',
    ]

    recommended_no_file_open = 524288
    required_components = ["OPENGL"]
    optional_components = ["VULKAN", "WINE", "GAMEMODE"]

    def __init__(self):
        for key in ("COMMANDS", "TERMINALS"):
            self._cache[key] = {}
            for command in SYSTEM_COMPONENTS[key]:
                command_path = shutil.which(command)
                if not command_path:
                    command_path = self.get_sbin_path(command)
                if command_path:
                    self._cache[key][command] = command_path

        # Detect if system is 64bit capable
        self.is_64_bit = sys.maxsize > 2 ** 32
        self.arch = self.get_arch()

        self.populate_libraries()
        self.populate_sound_fonts()
        self.soft_limit, self.hard_limit = self.get_file_limits()

    @staticmethod
    def get_sbin_path(command):
        """Some distributions don't put sbin directories in $PATH"""
        path_candidates = ["/sbin", "/usr/sbin"]
        for candidate in path_candidates:
            command_path = os.path.join(candidate, command)
            if os.path.exists(command_path):
                return command_path

    @staticmethod
    def get_file_limits():
        return resource.getrlimit(resource.RLIMIT_NOFILE)

    def has_enough_file_descriptors(self):
        return self.hard_limit >= self.recommended_no_file_open

    @staticmethod
    def get_arch():
        """Return the system architecture only if compatible
        with the supported architectures from the Lutris API
        """
        machine = platform.machine()
        if "64" in machine:
            return "x86_64"
        if "86" in machine:
            return "i386"
        if "armv7" in machine:
            return "armv7"
        logger.warning("Unsupported architecture %s", machine)

    @property
    def runtime_architectures(self):
        if self.arch == "x86_64":
            return ["i386", "x86_64"]
        return ["i386"]

    @property
    def requirements(self):
        return self.get_requirements()

    @property
    def critical_requirements(self):
        return self.get_requirements(include_optional=False)

    def get_requirements(self, include_optional=True):
        """Return used system requirements"""
        _requirements = self.required_components.copy()
        if include_optional:
            _requirements += self.optional_components
            if drivers.is_amd():
                _requirements.append("RADEON")
        return _requirements

    def get(self, command):
        """Return a system command path if available"""
        return self._cache["COMMANDS"].get(command)

    def get_terminals(self):
        """Return list of installed terminals"""
        return list(self._cache["TERMINALS"].values())

    def get_soundfonts(self):
        """Return path of available soundfonts"""
        return self._cache["SOUNDFONTS"]

    def iter_lib_folders(self):
        """Loop over existing 32/64 bit library folders"""
        for lib_paths in self.lib_folders:
            if self.arch != 'x86_64':
                # On non amd64 setups, only the first element is relevant
                lib_paths = [lib_paths[0]]
            if all([os.path.exists(path) for path in lib_paths]):
                yield lib_paths

    def populate_libraries(self):
        """Populates the LIBRARIES cache with what is found on the system"""
        self._cache["LIBRARIES"] = {}
        for arch in self.runtime_architectures:
            self._cache["LIBRARIES"][arch] = defaultdict(list)
        for lib_paths in self.iter_lib_folders():
            for req in self.requirements:
                for lib in SYSTEM_COMPONENTS["LIBRARIES"][req]:
                    for index, arch in enumerate(self.runtime_architectures):
                        if os.path.exists(os.path.join(lib_paths[index], lib)):
                            self._cache["LIBRARIES"][arch][req].append(lib)

    def populate_sound_fonts(self):
        """Populates the soundfont cache"""
        self._cache["SOUNDFONTS"] = []
        for folder in self.soundfont_folders:
            if not os.path.exists(folder):
                continue
            for soundfont in os.listdir(folder):
                self._cache["SOUNDFONTS"].append(soundfont)

    def get_missing_requirement_libs(self, req):
        """Return a list of sets of missing libraries for each supported architecture"""
        required_libs = set(SYSTEM_COMPONENTS["LIBRARIES"][req])
        return [
            required_libs - set(self._cache["LIBRARIES"][arch][req])
            for arch in self.runtime_architectures
        ]

    def get_missing_libs(self):
        """Return a dictionary of missing libraries"""
        return {
            req: self.get_missing_requirement_libs(req)
            for req in self.requirements
        }

    def is_feature_supported(self, feature):
        """Return whether the system has the necessary libs to support a feature"""
        return not self.get_missing_requirement_libs(feature)[0]


LINUX_SYSTEM = LinuxSystem()


def check_libs(all_components=False):
    """Checks that required libraries are installed on the system"""
    missing_libs = LINUX_SYSTEM.get_missing_libs()
    if all_components:
        components = LINUX_SYSTEM.requirements
    else:
        components = LINUX_SYSTEM.critical_requirements
    for req in components:
        for index, arch in enumerate(LINUX_SYSTEM.runtime_architectures):
            for lib in missing_libs[req][index]:
                logger.error("%s %s missing (needed by %s)", arch, lib, req.lower())


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
    if log_errors:
        stderr_handler = subprocess.PIPE
        stderr_needs_closing = False
    else:
        stderr_handler = open(os.devnull, "w")
        stderr_needs_closing = True
    try:
        stdout, stderr = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=stderr_handler,
            env=existing_env,
            cwd=cwd,
        ).communicate()
    except (OSError, TypeError) as ex:
        logger.error("Could not run command %s (env: %s): %s", command, env, ex)
        return
    finally:
        if stderr_needs_closing:
            stderr_handler.close()
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
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        logger.error("Could not kill process %s", pid)


def get_command_line(pid):
    """Return command line used to run the process `pid`."""
    cmdline = None
    cmdline_path = "/proc/{}/cmdline".format(pid)
    if os.path.exists(cmdline_path):
        with open(cmdline_path) as cmdline_file:
            cmdline = cmdline_file.read()
            cmdline = cmdline.replace("\x00", " ")
    return cmdline


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
        logger.warning("%s is a broken link")
        return not check_symlinks


def path_is_empty(path):
    """Return True is the given path doen't exist or it is an empty directory"""
    if not path_exists(path):
        return True
    return len(os.listdir(path)) == 0


def stacktrace():
    """Print a stacktrace at the current location"""
    traceback.print_stack()


def reset_library_preloads():
    """Remove library preloads from environment"""
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        if os.environ.get(key):
            del os.environ[key]


def get_desktop_environment():
    """Return the desktop environment currently being used"""
    # From http://stackoverflow.com/questions/2035657/what-is-my-current-desktop-environment
    # and http://ubuntuforums.org/showthread.php?t=652320
    # and http://ubuntuforums.org/showthread.php?t=652320
    # and http://ubuntuforums.org/showthread.php?t=1139057
    deskop_environments = [
        "gnome",
        "unity",
        "cinnamon",
        "mate",
        "xfce4",
        "lxde",
        "fluxbox",
        "blackbox",
        "openbox",
        "icewm",
        "jwm",
        "afterstep",
        "trinity",
        "kde",
    ]
    desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()
    if (
            desktop_session
    ):  # easier to match if we doesn't have to deal with caracter cases
        if desktop_session in deskop_environments:
            return desktop_session
        # Special cases
        # Canonical sets $DESKTOP_SESSION to Lubuntu rather than LXDE if using LXDE.
        if desktop_session.startswith("lubuntu"):
            return "lxde"
        if desktop_session.startswith("razor"):  # e.g. razorkwin
            return "razor-qt"
        if desktop_session.startswith("wmaker"):  # e.g. wmaker-common
            return "windowmaker"
    if os.environ.get("KDE_FULL_SESSION") == "true":
        return "kde"
    if os.environ.get("GNOME_DESKTOP_SESSION_ID"):
        if "deprecated" not in os.environ.get("GNOME_DESKTOP_SESSION_ID"):
            return "gnome2"
    # From http://ubuntuforums.org/showthread.php?t=652320
    elif is_running("xfce-mcs-manage"):
        return "xfce4"
    elif is_running("ksmserver"):
        return "kde"
    return "unknown"


def is_running(process):
    """Determines if a given process is currently running.

    The implementation looks brittle, unreliable and prone to false positives.
    """
    # From http://www.bloggerpolis.com/2011/05/how-to-check-if-a-process-is-running-using-python/
    # and http://richarddingwall.name/2009/06/18/windows-equivalents-of-ps-and-kill-commands/
    ps_process = subprocess.Popen(["ps", "axw"], stdout=subprocess.PIPE)
    for line in ps_process.stdout:
        if re.search(process, line):
            return True
    return False


def find_lib(libname):
    """Returns a list of absoulte paths found in the system of a given library"""
    lib_paths = []
    ldconfig_cmd = find_executable("ldconfig")
    if ldconfig_cmd:
        ldconfig_out = subprocess.check_output([ldconfig_cmd, "-p"]).decode("UTF-8")
        for out in ldconfig_out.splitlines():
            if libname in out:
                lib_paths.append(out.split("=> ")[1])
    else:
        logger.error("ldconfig not found, can't search for lib %s", libname)
    return lib_paths


def run_once(function):
    """Decorator to use on functions intended to run only once"""
    first_run = True

    def fn_wrapper(*args):
        nonlocal first_run
        if first_run:
            first_run = False
            return function(*args)
    return fn_wrapper
