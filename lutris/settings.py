"""Internal settings."""

import json
import os
import sys
from gettext import gettext as _

from gi.repository import GLib

from lutris import __version__
from lutris.util.log import logger
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = __version__
COPYRIGHT = _("(c) 2009 Lutris Team")
AUTHORS = [_("The Lutris team")]

# Paths
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "lutris")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "lutris")
if not os.path.exists(CONFIG_DIR):
    # Set the config dir to ~/.local/share/lutris as we're deprecating ~/.config/lutris
    CONFIG_DIR = DATA_DIR
CONFIG_FILE = os.path.join(CONFIG_DIR, "lutris.conf")
sio = SettingsIO(CONFIG_FILE)

RUNNER_DIR = sio.read_setting("runner_dir") or os.path.join(DATA_DIR, "runners")
RUNTIME_DIR = sio.read_setting("runtime_dir") or os.path.join(DATA_DIR, "runtime")
CACHE_DIR = sio.read_setting("cache_dir") or os.path.join(GLib.get_user_cache_dir(), "lutris")
TMP_DIR = os.path.join(CACHE_DIR, "tmp")
GAME_CONFIG_DIR = os.path.join(CONFIG_DIR, "games")
RUNNERS_CONFIG_DIR = os.path.join(CONFIG_DIR, "runners")

SHADER_CACHE_DIR = os.path.join(CACHE_DIR, "shaders")
INSTALLER_CACHE_DIR = os.path.join(CACHE_DIR, "installer")
BANNER_PATH = os.path.join(CACHE_DIR, "banners")
if not os.path.exists(BANNER_PATH):
    BANNER_PATH = os.path.join(DATA_DIR, "banners")
COVERART_PATH = os.path.join(CACHE_DIR, "coverart")
if not os.path.exists(COVERART_PATH):
    COVERART_PATH = os.path.join(DATA_DIR, "coverart")

RUNTIME_VERSIONS_PATH = os.path.join(CACHE_DIR, "versions.json")
ICON_PATH = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "128x128", "apps")

if "nosetests" in sys.argv[0] or "nose2" in sys.argv[0] or "pytest" in sys.argv[0]:
    DB_PATH = "/tmp/pga.db"
else:
    DB_PATH = sio.read_setting("pga_path") or os.path.join(DATA_DIR, "pga.db")

SITE_URL = sio.read_setting("website") or "https://lutris.net"

INSTALLER_URL = SITE_URL + "/api/installers/%s"

INSTALLER_REVISION_URL = SITE_URL + "/api/installers/game/%s/revisions/%s"
GAME_URL = SITE_URL + "/games/%s/"
RUNTIME_URL = SITE_URL + "/api/runtimes"

STEAM_API_KEY = sio.read_setting("steam_api_key") or "34C9698CEB394AB4401D65927C6B3752"
STEAM_FAMILY_INCLUDE_OWN = sio.read_setting("steam_family_include_own", default="False")

SHOW_MEDIA = os.environ.get("LUTRIS_HIDE_MEDIA") != "1" and sio.read_setting("hide_media") != "True"

DEFAULT_RESOLUTION_WIDTH = sio.read_setting("default_resolution_width", default="1280")
DEFAULT_RESOLUTION_HEIGHT = sio.read_setting("default_resolution_height", default="720")

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

UPDATE_CHANNEL_STABLE = "stable"
UPDATE_CHANNEL_UNSUPPORTED = "self-maintained"

read_setting = sio.read_setting
read_bool_setting = sio.read_bool_setting
write_setting = sio.write_setting
SETTINGS_CHANGED = sio.SETTINGS_CHANGED


def get_lutris_directory_settings(directory):
    """Reads the 'lutris.json' file in 'directory' and returns it as
    a (new) dictionary. The file is missing, unreadable, unparseable, or not a dict,
    this returns an empty dict instead."""
    if directory:
        path = os.path.join(directory, "lutris.json")
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                    if not isinstance(json_data, dict):
                        logger.error("'%s' does not contain a dict, and will be ignored.", path)
                    return json_data
        except Exception as ex:
            logger.exception("Failed to read '%s': %s", path, ex)
    return {}


def set_lutris_directory_settings(directory, settings, merge=True):
    """Updates the 'lutris.json' file in the 'directory' given. If it does not exist, this method creates it. By
    default, if it does exist this merges the values of settings into it, but in a shallow way - only the top level
    entries are merged, not the content any of any sub-dictionaries. If 'merge' is False, this replaces the existing
    'lutris.json', so that its settings are lost.

    This function provides no way to remove a key; you can store nulls instead if appropriate.\

    If this 'lutris.json' file can't be updated (say, if 'settings' can't be represented) then this
    logs the errors, but then returns False."""
    path = os.path.join(directory, "lutris.json")
    if merge and os.path.isfile(path):
        old_settings = get_lutris_directory_settings(directory)
        old_settings.update(settings)
        settings = old_settings

    # In case settings contains something that can't be made into JSON
    # we'll save to a temporary file and rename.
    temp_path = os.path.join(directory, "lutris.json.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(settings, indent=2))
        os.rename(temp_path, path)
        return True
    except Exception as ex:
        logger.exception("Could not update '%s': %s", path, ex)
        return False
    finally:
        if os.path.isfile(temp_path):
            os.unlink(temp_path)
