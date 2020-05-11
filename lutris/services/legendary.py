"""Module for handling the Legendary (Epic Games) service"""
# Standard Library
import json
import os
import time
from urllib.parse import parse_qsl, urlencode, urlparse

# Lutris Modules
from lutris import api, pga, settings
from lutris.gui.dialogs import WebConnectDialog
from lutris.services import AuthenticationError, UnavailableGame
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.util import system
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger
from lutris.util.resources import download_media
from lutris.runners.legendary import legendary
import subprocess
import io
from lutris.util.strings import slugify

NAME = "Legendary (Epic Store)"
ICON = "legendary"
ONLINE = True


class MultipleInstallerError(BaseException):

    """Current implementation doesn't know how to deal with multiple installers
    Raise this if a game returns more than 1 installer."""


class LegendaryService(OnlineService):

    """Service class for Legendary (Epic Games)"""

    name = "Legendary"
    runner = legendary()

    @property
    def credential_files(self):
        return [
            os.path.expanduser("~/.config/legendary/user.json")
        ]

    def is_available(self):
        """Return whether the user is authenticated and if the service is available"""
        if not self.runner.is_installed():
            return False
        return self.is_authenticated()

    def get_library(self):
        """Return the user's library of Epic Store games"""
        getcmd = subprocess.Popen(
            [self.runner.get_executable(), "list-games", "--csv"],
            stdout=subprocess.PIPE
        )
        lines = io.TextIOWrapper(getcmd.stdout, encoding="utf-8").readlines()
        return list(lines)[1:] # skip the csv header


class EGSGame(ServiceGame):

    """Representation of a EGS game"""
    store = "egs"

    @classmethod
    def new_from_legendary_csv(cls, legendary_csv):
        parts = legendary_csv.split(",")
        """Return a GOG game instance from the API info"""
        service_game = EGSGame()
        service_game.appid = str(parts[0])
        service_game.name = parts[1]
        service_game.details = legendary_csv
        return service_game


SERVICE = LegendaryService()


def is_connected():
    """Return True if user is connected to GOG"""
    return SERVICE.is_available()


def connect(parent=None):
    """Authenticate Legendary"""
    logger.debug("Connecting Legendary to EGS")


def disconnect():
    """Disconnect Legendary from EGS"""
    SERVICE.disconnect()


class GOGSyncer:

    """Sync GOG games to Lutris"""

    @classmethod
    def load(cls):
        """Load the user game library from the GOG API"""
        return [EGSGame.new_from_legendary_csv(game) for game in SERVICE.get_library()]

    @classmethod
    def sync(cls, games, full=False):
        """Import EGS games to the Lutris library"""
        added_games = []
        for game in games:
            game_data = {
                "name": game.name,
                "slug": slugify(game.name)
            }
            added_games.append(pga.add_or_update(**game_data))
        if not full:
            return added_games, games
        return added_games, []


SYNCER = GOGSyncer
