"""Utility module for creating an application wide logger."""
import os
import sys
import logging
import logging.handlers
from gi.repository import GLib


CACHE_DIR = os.path.realpath(os.path.join(GLib.get_user_cache_dir(), "lutris"))
if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Formatters
FILE_FORMATTER = logging.Formatter(
    "[%(levelname)s:%(asctime)s:%(module)s]: %(message)s"
)

SIMPLE_FORMATTER = logging.Formatter("%(asctime)s: %(message)s")

DEBUG_FORMATTER = logging.Formatter(
    "%(levelname)-8s %(asctime)s [%(module)s.%(funcName)s:%(lineno)s]:%(message)s"
)

# Log file setup
LOG_FILENAME = os.path.join(CACHE_DIR, "lutris.log")
loghandler = logging.handlers.RotatingFileHandler(
    LOG_FILENAME, maxBytes=20971520, backupCount=5
)
loghandler.setFormatter(FILE_FORMATTER)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(loghandler)

# Set the logging level to show debug messages.
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(SIMPLE_FORMATTER)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)
