"""Internal settings."""
import os
import sys
from gettext import gettext as _

from gi.repository import GLib

from lutris import __version__
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = __version__
COPYRIGHT = _("(c) 2010-2021 Lutris Team")
AUTHORS = [_("The Lutris team")]

# Paths
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "lutris")
CONFIG_FILE = os.path.join(CONFIG_DIR, "lutris.conf")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "lutris")
RUNNER_DIR = os.path.join(DATA_DIR, "runners")
RUNTIME_DIR = os.path.join(DATA_DIR, "runtime")
CACHE_DIR = os.path.join(GLib.get_user_cache_dir(), "lutris")
GAME_CONFIG_DIR = os.path.join(CONFIG_DIR, "games")

TMP_PATH = os.path.join(CACHE_DIR, "tmp")
SHADER_CACHE_DIR = os.path.join(CACHE_DIR, "shaders")
BANNER_PATH = os.path.join(CACHE_DIR, "banners")
COVERART_PATH = os.path.join(DATA_DIR, "coverart")
ICON_PATH = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "128x128", "apps")

sio = SettingsIO(CONFIG_FILE)
if "nosetests" in sys.argv[0] or "pytest" in sys.argv[0]:
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


read_setting = sio.read_setting
write_setting = sio.write_setting
