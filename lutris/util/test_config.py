import os

from lutris.database import schema
from lutris.startup import init_lutris


def setup_test_environment():
    """Sets up a system to be able to run tests"""
    os.environ["LUTRIS_SKIP_INIT"] = "1"
    schema.syncdb()
    init_lutris()
