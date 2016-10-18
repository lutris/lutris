import hashlib
import os
import re
import shutil
import string
import subprocess
import sys
import traceback

from lutris.util.log import logger


TERMINAL_CANDIDATES = [
    'xterm',
    'gnome-terminal',
    'konsole',
    'xfce4-terminal',
    'pantheon-terminal',
    'terminator',
    'urxvt',
    'cool-retro-term',
    'Eterm',
    'guake',
    'lilyterm',
    'lxterminal',
    'roxterm',
    'rxvt',
    'aterm',
    'sakura',
    'st',
    'terminology',
    'termite',
    'wterm',
    'yuakuake',
]

INSTALLED_TERMINALS = []

is_64bit = sys.maxsize > 2**32


def execute(command, env=None, cwd=None, log_errors=False):
    """Execute a system command and return its results."""
    existing_env = os.environ.copy()
    if env:
        existing_env.update(env)
        logger.debug(' '.join('{}={}'.format(k, v) for k, v in env.items()))
    logger.debug("Executing %s", ' '.join(command))

    # Piping stderr can cause slowness in the programs, use carefully
    # (especially when using regedit with wine)
    if log_errors:
        stderr_handler = subprocess.PIPE
        stderr_needs_closing = False
    else:
        stderr_handler = open(os.devnull, 'w')
        stderr_needs_closing = True
    try:
        stdout, stderr = subprocess.Popen(command,
                                          shell=False,
                                          stdout=subprocess.PIPE,
                                          stderr=stderr_handler,
                                          env=existing_env, cwd=cwd).communicate()
    except OSError as ex:
        logger.error('Could not run command %s: %s', command, ex)
        return
    finally:
        if stderr_needs_closing:
            stderr_handler.close()
    if stderr and log_errors:
        logger.error(stderr)
    return stdout.decode().strip()


def get_md5_hash(filename):
    """Return the md5 hash of a file."""
    md5 = hashlib.md5()
    try:
        with open(filename, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
    except IOError:
        print("Error reading %s" % filename)
        return False
    return md5.hexdigest()


def find_executable(exec_name):
    if not exec_name:
        raise ValueError("find_executable: exec_name required")
    return execute(['which', exec_name])


def get_pid(program, multiple=False):
    """Return pid of process.

    :param str program: Name of the process.
    :param bool multiple: If True and multiple instances of the program exist,
        return all of them; if False only return the first one.
    """
    pids = execute(['pgrep', program])
    if not pids.strip():
        return
    pids = pids.split()
    if multiple:
        return pids
    else:
        return pids[0]


def kill_pid(pid):
    try:
        int(pid)
    except ValueError:
        logger.error("Invalid pid %s")
        return
    execute(['kill', '-9', pid])


def get_command_line(pid):
    """Return command line used to run the process `pid`."""
    cmdline = None
    cmdline_path = '/proc/{}/cmdline'.format(pid)
    if os.path.exists(cmdline_path):
        with open(cmdline_path) as cmdline_file:
            cmdline = cmdline_file.read()
            cmdline = cmdline.replace('\x00', ' ')
    return cmdline


def python_identifier(string):
    if not isinstance(string, str):
        logger.error("python_identifier requires a string, got %s", string)
        return

    def dashrepl(matchobj):
        return matchobj.group(0).replace('-', '_')

    return re.sub(r'(\${)([\w-]*)(})', dashrepl, string)


def substitute(fileid, files):
    fileid = python_identifier(str(fileid))
    files = dict((k.replace('-', '_'), v) for k, v in list(files.items()))
    template = string.Template(fileid)
    if fileid in list(files.keys()):
        return files[fileid]
    return template.safe_substitute(files)


def merge_folders(source, destination):
    logger.debug("Merging %s into %s", source, destination)
    source = os.path.abspath(source)
    for (dirpath, dirnames, filenames) in os.walk(source):
        source_relpath = dirpath[len(source):].strip('/')
        dst_abspath = os.path.join(destination, source_relpath)
        for dirname in dirnames:
            new_dir = os.path.join(dst_abspath, dirname)
            logger.debug("creating dir: %s" % new_dir)
            try:
                os.mkdir(new_dir)
            except OSError:
                pass
        for filename in filenames:
            logger.debug("Copying %s" % filename)
            if not os.path.exists(dst_abspath):
                os.makedirs(dst_abspath)
            shutil.copy(os.path.join(dirpath, filename),
                        os.path.join(dst_abspath, filename))


def remove_folder(path):
    if os.path.exists(path):
        logger.debug("Removing folder %s" % path)
        if os.path.samefile(os.path.expanduser('~'), path):
            raise RuntimeError("Lutris tried to erase home directory!")
        shutil.rmtree(path)


def create_folder(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def is_removeable(path, excludes=None):
    """Check if a folder is safe to remove (not system or home, ...)"""
    if not path:
        return False
    if not os.path.exists(path):
        return False
    if path in excludes:
        return False

    parts = path.strip('/').split('/')
    if parts[0] in ('usr', 'var', 'lib', 'etc', 'boot', 'sbin', 'bin'):
        # Path is part of the system folders
        return False

    if parts[0] == 'home':
        if len(parts) <= 2:
            # Path is a home folder
            return False
        if parts[2] == '.wine':
            # Protect main .wine folder
            return False

    return True


def fix_path_case(path):
    """Do a case insensitive check, return the real path with correct case."""
    if os.path.exists(path):
        return path
    parts = path.strip('/').split('/')
    current_path = "/"
    for part in parts:
        if not os.path.exists(current_path):
            return
        tested_path = os.path.join(current_path, part)
        if os.path.exists(tested_path):
            current_path = tested_path
            continue
        for filename in os.listdir(current_path):
            if filename.lower() == part.lower():
                current_path = os.path.join(current_path, filename)
                continue

    # Only return the path if we got the same number of elements
    if len(parts) == len(current_path.strip('/').split('/')):
        return current_path


def get_pids_using_file(path):
    """Return a set of pids using file `path`."""
    if not os.path.exists(path):
        logger.error("No file %s", path)
        return set()
    fuser_output = []
    if os.path.exists('/bin/fuser'):
        fuser_output = execute(["fuser", path])
    else:
        fuser_output = execute(["/sbin/fuser", path])
    return set(fuser_output.split())


def get_terminal_apps():
    if INSTALLED_TERMINALS:
        return INSTALLED_TERMINALS
    else:
        for exe in TERMINAL_CANDIDATES:
            if find_executable(exe):
                INSTALLED_TERMINALS.append(exe)
    return INSTALLED_TERMINALS


def get_default_terminal():
    terms = get_terminal_apps()
    if terms:
        return terms[0]
    else:
        logger.debug("Couldn't find a terminal emulator.")


def reverse_expanduser(path):
    """Replace '/home/username' with '~' in given path."""
    if not path:
        return path
    user_path = os.path.expanduser('~')
    if path.startswith(user_path):
        path = path[len(user_path):].strip('/')
        return '~/' + path
    return path


def path_exists(path):
    if not path:
        return False
    return os.path.exists(path)


def stacktrace():
    traceback.print_stack()
