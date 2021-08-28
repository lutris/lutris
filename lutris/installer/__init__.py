"""Install script interpreter package."""
import yaml

from lutris import settings
from lutris.util import system
from lutris.util.http import Request
from lutris.util.log import logger

AUTO_ELF_EXE = "_xXx_AUTO_ELF_xXx_"
AUTO_WIN32_EXE = "_xXx_AUTO_WIN32_xXx_"


def fetch_script(game_slug, revision=None):
    """Download install script(s) for matching game_slug."""
    if not game_slug:
        raise ValueError("No game_slug provided. Can't query an installer")
    if revision:
        installer_url = settings.INSTALLER_REVISION_URL % (game_slug, revision)
    else:
        installer_url = settings.INSTALLER_URL % game_slug

    logger.debug("Fetching installer %s", installer_url)
    request = Request(installer_url)
    request.get()
    response = request.json
    if response is None:
        raise RuntimeError("Couldn't get installer at %s" % installer_url)

    if not revision:
        return response["results"]
    # Revision requests return a single installer
    return [response]


def read_script(filename):
    """Return scripts from a local file"""
    logger.debug("Loading script(s) from %s", filename)
    script = yaml.safe_load(open(filename).read())
    if isinstance(script, list):
        return script
    if "results" in script:
        return script["results"]
    return [script]


def get_installers(game_slug, installer_file=None, revision=None):
    # check if installer is local or online
    if system.path_exists(installer_file):
        return read_script(installer_file)
    return fetch_script(game_slug=game_slug, revision=revision)
