"""Utility module for creating an application wide logger."""

import logging
import logging.handlers
import os
import sys

from gi.repository import GLib

# Used to store log buffers for games.
LOG_BUFFERS = {}

CACHE_DIR = os.path.realpath(os.path.join(GLib.get_user_cache_dir(), "lutris"))
if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Formatters
FILE_FORMATTER = logging.Formatter("[%(levelname)s:%(asctime)s:%(module)s]: %(message)s")
SIMPLE_FORMATTER = logging.Formatter("%(asctime)s: %(message)s")
DEBUG_FORMATTER = logging.Formatter("%(levelname)-8s %(asctime)s [%(module)s.%(funcName)s:%(lineno)s]:%(message)s")

# Log file setup
LOG_FILENAME = os.path.join(CACHE_DIR, "lutris.log")
file_handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, backupCount=5)
file_handler.setFormatter(FILE_FORMATTER)

file_logger = logging.getLogger(__name__)
file_logger.setLevel(logging.DEBUG)
file_logger.addHandler(file_handler)

# Set the logging level to show debug messages.
console_handler = logging.StreamHandler(stream=sys.stderr)
console_handler.setFormatter(SIMPLE_FORMATTER)

logger = logging.getLogger(__name__)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def get_log_contents():
    """Returns the entire text of the log file for this run."""
    if not os.path.exists(LOG_FILENAME):
        return ""
    with open(LOG_FILENAME, encoding="utf-8") as log_file:
        content = log_file.read()
    return content
