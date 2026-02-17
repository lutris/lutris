"""Migrate Proton versions from the old runners/proton directory to runners/wine"""

import os

from lutris import settings
from lutris.util.log import logger


def migrate():
    src_dir = os.path.join(settings.RUNNER_DIR, "proton")
    dest_dir = settings.WINE_DIR

    if not os.path.isdir(src_dir):
        return

    try:
        os.makedirs(dest_dir, exist_ok=True)

        for entry in os.listdir(src_dir):
            src_path = os.path.join(src_dir, entry)
            dest_path = os.path.join(dest_dir, entry)

            if not os.path.isdir(src_path):
                continue

            if os.path.exists(dest_path):
                logger.info("Skipping '%s', already exists in %s", entry, dest_dir)
            else:
                logger.info("Moving Proton version '%s' to %s", entry, dest_dir)
                os.rename(src_path, dest_path)

        if not os.listdir(src_dir):
            os.rmdir(src_dir)
    except OSError as ex:
        logger.exception("Failed to migrate Proton versions: %s", ex)
