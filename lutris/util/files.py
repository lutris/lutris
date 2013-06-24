import hashlib
import subprocess


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
