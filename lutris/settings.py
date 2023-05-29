"""Internal settings."""
import json
import os
import sys
from gettext import gettext as _
from json import JSONDecodeError

from gi.repository import GLib

from lutris import __version__
from lutris.util import selective_merge
from lutris.util.log import logger
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = __version__
COPYRIGHT = _("(c) 2009 Lutris Team")
AUTHORS = [_("The Lutris team")]

# Paths
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "lutris")
CONFIG_FILE = os.path.join(CONFIG_DIR, "lutris.conf")
sio = SettingsIO(CONFIG_FILE)

DATA_DIR = os.path.join(GLib.get_user_data_dir(), "lutris")
RUNNER_DIR = sio.read_setting("runner_dir") or os.path.join(DATA_DIR, "runners")
RUNTIME_DIR = sio.read_setting("runtime_dir") or os.path.join(DATA_DIR, "runtime")
CACHE_DIR = sio.read_setting("cache_dir") or os.path.join(GLib.get_user_cache_dir(), "lutris")
GAME_CONFIG_DIR = os.path.join(CONFIG_DIR, "games")

TMP_PATH = os.path.join(CACHE_DIR, "tmp")
SHADER_CACHE_DIR = os.path.join(CACHE_DIR, "shaders")
BANNER_PATH = os.path.join(CACHE_DIR, "banners")
COVERART_PATH = os.path.join(CACHE_DIR, "coverart")
ICON_PATH = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "128x128", "apps")

if "nosetests" in sys.argv[0] or "nose2" in sys.argv[0] or "pytest" in sys.argv[0]:
    PGA_DB = "/tmp/pga.db"
else:
    PGA_DB = sio.read_setting("pga_path") or os.path.join(DATA_DIR, "pga.db")

SITE_URL = sio.read_setting("website") or "https://lutris.net"

DRIVER_HOWTO_URL = "https://github.com/lutris/docs/blob/master/InstallingDrivers.md"
INSTALLER_URL = SITE_URL + "/api/installers/%s"

INSTALLER_REVISION_URL = SITE_URL + "/api/installers/game/%s/revisions/%s"
GAME_URL = SITE_URL + "/games/%s/"
RUNTIME_URL = SITE_URL + "/api/runtimes"

STEAM_API_KEY = sio.read_setting("steam_api_key") or "34C9698CEB394AB4401D65927C6B3752"

SHOW_MEDIA = os.environ.get("LUTRIS_HIDE_MEDIA") != "1" and sio.read_setting("hide_media") != 'True'

DEFAULT_RESOLUTION_WIDTH = 1280
DEFAULT_RESOLUTION_HEIGHT = 720

read_setting = sio.read_setting
write_setting = sio.write_setting


def get_lutris_directory_settings(directory):
    path = os.path.join(directory, "lutris.json")
    if os.path.isfile(path):
        with open(path, "r", encoding='utf-8') as f:
            return json.load(f)
    return {}


def set_lutris_directory_settings(directory, settings, merge=True):
    path = os.path.join(directory, "lutris.json")
    if merge and not os.path.isfile(path):
        merge = False

    with open(path, "r+" if merge else "w", encoding='utf-8') as f:
        if merge:
            try:
                json_data = json.load(f)
            except JSONDecodeError:
                logger.error("Failed to parse JSON from file %s", path)
                json_data = {}
            json_data = selective_merge(json_data, settings)
        else:
            json_data = settings

        f.seek(0)
        f.write(json.dumps(json_data, indent=2))
