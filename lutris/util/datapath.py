"""Utility to get the path of Lutris assets"""
import os
import sys
from lutris.util import system


def get():
    """Return the path for the resources."""
    launch_path = os.path.realpath(sys.path[0])
    if launch_path.startswith("/usr/local"):
        data_path = "/usr/local/share/lutris"
    elif launch_path.startswith("/usr"):
        data_path = "/usr/share/lutris"
    elif system.path_exists(os.path.normpath(os.path.join(sys.path[0], "share"))):
        data_path = os.path.normpath(os.path.join(sys.path[0], "share/lutris"))
    elif system.path_exists(os.path.normpath(os.path.join(launch_path, "../../share/lutris"))):
        data_path = os.path.normpath(os.path.join(launch_path, "../../share/lutris"))
    else:
        import lutris

        lutris_module = lutris.__file__
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(lutris_module)), "share/lutris"
        )
    if not system.path_exists(data_path):
        raise IOError("data_path can't be found at : %s" % data_path)
    return data_path
