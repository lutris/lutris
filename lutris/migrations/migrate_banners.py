"""Migrate banners from .local/share/lutris to .cache/lutris"""
import os

from lutris import settings


def migrate():
    dest_dir = settings.BANNER_PATH
    src_dir = os.path.join(settings.DATA_DIR, "banners")

    # init_lutris() creates the new banners directrory
    if os.path.isdir(src_dir) and os.path.isdir(dest_dir):
        for filename in os.listdir(src_dir):
            try:
                src_file = os.path.join(src_dir, filename)
                dest_file = os.path.join(dest_dir, filename)

                if not os.path.exists(dest_file):
                    os.rename(src_file, dest_file)
            except OSError:
                pass  # Skip what we can't migrate
