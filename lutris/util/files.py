import re
import string
import hashlib
import subprocess

from lutris.util.log import logger


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
    result = subprocess.Popen(['which', exec_name],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).communicate()[0]
    return result


def python_identifier(string):
    if not isinstance(string, basestring):
        logger.error("python_identifier requires a string, got %s", string)
        return

    def dashrepl(matchobj):
        return matchobj.group(0).replace('-', '_')

    return re.sub(r'(\${)([\w-]*)(})', dashrepl, string)


def substitute(fileid, files):
    fileid = python_identifier(fileid)
    files = dict((k.replace('-', '_'), v) for k, v in files.items())
    template = string.Template(fileid)
    return template.safe_substitute(files)
