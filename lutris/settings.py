"""Internal settings."""
# Standard Library
import os
from gettext import gettext as _

# Third Party Libraries
from gi.repository import GLib

# Lutris Modules
from lutris import __version__
from lutris.util.settings import SettingsIO

PROJECT = _("Lutris")
VERSION = __version__
COPYRIGHT = _("(c) 2010-2020 Lutris Gaming Platform")
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
BANNER_PATH = os.path.join(DATA_DIR, "banners")
COVERART_PATH = os.path.join(DATA_DIR, "coverart")
ICON_PATH = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "128x128", "apps")

sio = SettingsIO(CONFIG_FILE)
PGA_DB = sio.read_setting("pga_path") or os.path.join(DATA_DIR, "pga.db")
SITE_URL = sio.read_setting("website") or "https://lutris.net"

INSTALLER_URL = SITE_URL + "/api/installers/%s"
# XXX change this, should query on the installer, not the game.
INSTALLER_REVISION_URL = SITE_URL + "/api/installers/games/%s/revisions/%s"
GAME_URL = SITE_URL + "/games/%s/"
ICON_URL = SITE_URL + "/games/icon/%s.png"
BANNER_URL = SITE_URL + "/games/banner/%s.jpg"
RUNTIME_URL = "https://lutris.net/api/runtime"

DEFAULT_DISCORD_CLIENT_ID = "618290412402114570"

read_setting = sio.read_setting
write_setting = sio.write_setting
