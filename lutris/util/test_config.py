import os


def setup_test_environment():
    """Sets up a system to be able to run tests"""
    os.environ["LUTRIS_SKIP_INIT"] = "1"
