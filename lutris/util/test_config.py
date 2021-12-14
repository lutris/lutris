import os

import gi
gi.require_version('Gtk', '3.0')

from lutris import startup
from lutris.database import schema


def setup_test_environment():
    """Sets up a system to be able to run tests"""
    os.environ["LUTRIS_SKIP_INIT"] = "1"
    schema.syncdb()
    startup.init_lutris()
