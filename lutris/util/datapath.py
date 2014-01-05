import os
import sys


def get():
    """ Returns the path for the resources. """
    launch_path = os.path.realpath(sys.path[0])
    if launch_path.startswith("/usr/local"):
        data_path = '/usr/local/share/lutris'
    elif launch_path.startswith("/usr"):
        data_path = '/usr/share/lutris'
    elif os.path.exists(os.path.normpath(os.path.join(sys.path[0], 'data'))):
        data_path = os.path.normpath(os.path.join(sys.path[0], 'data'))
    else:
        import lutris
        data_path = os.path.dirname(lutris.__file__)
    if not os.path.exists(data_path):
        print("data_path can't be found at : %s" % data_path)
        exit()
    return data_path
