import os
import re
import shutil
import string
import hashlib
import subprocess

from lutris.util.log import logger


def execute(command):
    """ Execute a system command and result its results """
    stdout, stderr = subprocess.Popen(command,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE).communicate()
    return stdout.strip()


def calculate_md5(filename):
    """ Return the md5 hash of filename. """
    md5 = hashlib.md5()
    try:
        with open(filename, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
    except IOError:
        print "Error reading %s" % filename
        return False
    return md5.hexdigest()


def find_executable(exec_name):
    if not exec_name:
        raise ValueError("find_executable: exec_name required")
    return execute(['which', exec_name])


def get_pid(program):
    return execute(['pgrep', program])


def kill_pid(pid):
    assert str(int(pid)) == str(pid)
    execute(['kill', '-9', pid])


def get_cwd(pid):
    cwd_file = '/proc/%d/cwd' % int(pid)
    if not os.path.exists(cwd_file):
        return False
    return os.readlink(cwd_file)


def get_command_line(pid):
    cmdline_path = '/proc/%d/cmdline' % int(pid)
    if not os.path.exists(cmdline_path):
        return False
    return open(cmdline_path, 'r').read().replace('\x00', ' ').strip()


def python_identifier(string):
    if not isinstance(string, basestring):
        logger.error("python_identifier requires a string, got %s", string)
        return

    def dashrepl(matchobj):
        return matchobj.group(0).replace('-', '_')

    return re.sub(r'(\${)([\w-]*)(})', dashrepl, string)


def substitute(fileid, files):
    fileid = python_identifier(str(fileid))
    files = dict((k.replace('-', '_'), v) for k, v in files.items())
    template = string.Template(fileid)
    if fileid in files.keys():
        return files[fileid]
    return template.safe_substitute(files)


def merge_folders(source, destination):
    logger.debug("Merging %s into %s", source, destination)
    for (dirpath, dirnames, filenames) in os.walk(source):
        source_relpath = dirpath[len(source) + 1:]
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
