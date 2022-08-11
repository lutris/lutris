"""Internal settings."""
import os
import sys
from gettext import gettext as _

from gi.repository import GLib

from lutris import __version__
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = __version__
COPYRIGHT = _("(c) 2010-2022 Lutris Team")
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
# XXX change this, should query on the installer, not the game.
INSTALLER_REVISION_URL = SITE_URL + "/api/installers/games/%s/revisions/%s"
GAME_URL = SITE_URL + "/games/%s/"
RUNTIME_URL = SITE_URL + "/api/runtimes"

STEAM_API_KEY = sio.read_setting("steam_api_key") or "34C9698CEB394AB4401D65927C6B3752"
DISCORD_CLIENT_ID = sio.read_setting("discord_client_id") or "618290412402114570"

SHOW_MEDIA = os.environ.get("LUTRIS_HIDE_MEDIA") != "1" and sio.read_setting("hide_media") != 'True'

DEFAULT_RESOLUTION_WIDTH = 1280
DEFAULT_RESOLUTION_HEIGHT = 720

read_setting = sio.read_setting
write_setting = sio.write_setting
