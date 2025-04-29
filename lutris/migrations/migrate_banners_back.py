"""Migrate banners and coverart from .cache/lutris to .local/share/lutris"""

import os

from lutris import settings
from lutris.util.log import logger


def _migrate(dirname):
    dest_dir = os.path.join(settings.DATA_DIR, dirname)
    src_dir = os.path.join(settings.CACHE_DIR, dirname)

    try:
        # init_lutris() creates the new banners directory
        if os.path.isdir(src_dir) and os.path.isdir(dest_dir):
            for filename in os.listdir(src_dir):
                src_file = os.path.join(src_dir, filename)
                dest_file = os.path.join(dest_dir, filename)

                if not os.path.exists(dest_file):
                    os.rename(src_file, dest_file)
                else:
                    os.unlink(src_file)

            if not os.listdir(src_dir):
                os.rmdir(src_dir)
    except OSError as ex:
        logger.exception("Failed to migrate banners: %s", ex)


def migrate():
    _migrate("banners")
    _migrate("coverart")
