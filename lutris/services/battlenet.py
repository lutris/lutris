"""Battle.net service"""

import json
import os
from gettext import gettext as _

from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.services.base import BaseService
from lutris.services.lutris import sync_media
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.battlenet.definitions import ProductDbInfo
from lutris.util.log import logger

try:
    from lutris.util.battlenet.product_db_pb2 import ProductDb

    BNET_ENABLED = True
except Exception as ex:
    # We do get strange Google-defined exceptions from problems with protobuf, so
    # let's just catch (almost) everything. We do not want Lutris is crash, rather
    # we just want to suppress Battle.net and nothing else.
    logger.warning("The Battle.net source is unavailable because Google protobuf could not be loaded: %s", ex)
    BNET_ENABLED = False

GAME_IDS = {
    "s1": ("s1", "StarCraft", "S1", "starcraft-remastered"),
    "s2": ("s2", "StarCraft II", "S2", "starcraft-ii"),
    "wow": ("wow", "World of Warcraft", "WoW", "world-of-warcraft"),
    "wow_classic": ("wow_classic", "World of Warcraft Classic", "WoW_wow_classic", "world-of-warcraft-classic"),
    "pro": ("pro", "Overwatch 2", "Pro", "overwatch-2"),
    "w2bn": ("w2bn", "Warcraft II: Battle.net Edition", "W2BN", "warcraft-ii-battle-net-edition"),
    "w3": ("w3", "Warcraft III", "W3", "warcraft-iii-reforged"),
    "hsb": ("hsb", "Hearthstone", "WTCG", "hearthstone"),
    "hero": ("hero", "Heroes of the Storm", "Hero", "heroes-of-the-storm"),
    "d3cn": ("d3cn", "暗黑破壞神III", "D3CN", "diablo-iii"),
    "d3": ("d3", "Diablo III", "D3", "diablo-iii"),
    "fenris": ("fenris", "Diablo IV", "Fen", "diablo-iv"),
    "viper": ("viper", "Call of Duty: Black Ops 4", "VIPR", "call-of-duty-black-ops-4"),
    "odin": ("odin", "Call of Duty: Modern Warfare", "ODIN", "call-of-duty-modern-warfare"),
    "lazarus": (
        "lazarus",
        "Call of Duty: MW2 Campaign Remastered",
        "LAZR",
        "call-of-duty-modern-warfare-2-campaign-remastered",
    ),
    "zeus": ("zeus", "Call of Duty: Black Ops Cold War", "ZEUS", "call-of-duty-black-ops-cold-war"),
    "rtro": ("rtro", "Blizzard Arcade Collection", "RTRO", "blizzard-arcade-collection"),
    "wlby": ("wlby", "Crash Bandicoot 4: It's About Time", "WLBY", "crash-bandicoot-4-its-about-time"),
    "osi": ("osi", "Diablo® II: Resurrected", "OSI", "diablo-2-ressurected"),
    "fore": ("fore", "Call of Duty: Vanguard", "FORE", "call-of-duty-vanguard"),
    "d2": ("d2", "Diablo® II", "Diablo II", "diablo-ii"),
    "d2LOD": ("d2LOD", "Diablo® II: Lord of Destruction®", "Diablo II", "diablo-ii-lord-of-destruction"),
    "w3ROC": ("w3ROC", "Warcraft® III: Reign of Chaos", "Warcraft III", "warcraft-iii-reign-of-chaos"),
    "w3tft": ("w3tft", "Warcraft® III: The Frozen Throne®", "Warcraft III", "warcraft-iii-the-frozen-throne"),
    "sca": ("sca", "StarCraft® Anthology", "Starcraft", "starcraft"),
    "anbs": ("anbs", "Diablo Immortal", "ANBS", "diablo-immortal"),
}


class BattleNetCover(ServiceMedia):
    service = "battlenet"
    size = (176, 234)
    file_patterns = ["%s.jpg"]
    dest_path = os.path.join(settings.CACHE_DIR, "battlenet/coverart")
    api_field = "coverart"


class BattleNetGame(ServiceGame):
    """Game from Battle.net"""

    service = "battlenet"
    runner = "wine"
    installer_slug = "battlenet"

    @classmethod
    def create(cls, blizzard_game):
        """Create a service game from an entry from the Dolphin cache"""
        service_game = cls()
        service_game.appid = blizzard_game[0]
        service_game.name = blizzard_game[1]
        service_game.slug = blizzard_game[3]
        service_game.details = json.dumps(
            {
                "id": blizzard_game[0],
                "name": blizzard_game[1],
                "product_code": blizzard_game[2],
                "slug": blizzard_game[3],
                "coverart": "https://lutris.net/games/cover/%s.jpg" % blizzard_game[3],
            }
        )
        return service_game


class BattleNetService(BaseService):
    """Service class for Battle.net"""

    id = "battlenet"
    name = _("Battle.net")
    icon = "battlenet"
    runner = "wine"
    medias = {"coverart": BattleNetCover}
    default_format = "coverart"
    client_installer = "battlenet"
    cookies_path = os.path.join(settings.CACHE_DIR, ".bnet.auth")
    cache_path = os.path.join(settings.CACHE_DIR, "bnet-library.json")
    redirect_uris = ["https://lutris.net"]

    @property
    def battlenet_config_path(self):
        return ""

    def load(self):
        games = [BattleNetGame.create(game) for game in GAME_IDS.values()]
        for game in games:
            game.save()
        return games

    def add_installed_games(self):
        """Scan an existing Battle.net install for games"""
        bnet_game = get_game_by_field(self.client_installer, "slug")
        if not bnet_game:
            raise RuntimeError("Battle.net is not installed in Lutris")
        bnet_prefix = bnet_game["directory"].split("drive_c")[0]
        parser = BlizzardProductDbParser(bnet_prefix)
        installed_slugs = []
        for game in parser.games:
            slug = self.install_from_battlenet(bnet_game, game)
            if slug:
                installed_slugs.append(slug)
        sync_media(installed_slugs)

    def install_from_battlenet(self, bnet_game, game):
        app_id = game.ngdp
        logger.debug("Installing Battle.net game %s", app_id)
        service_game = ServiceGameCollection.get_game("battlenet", app_id)
        if not service_game:
            logger.error("Aborting install, %s is not present in the game library.", app_id)
            return
        lutris_game_id = service_game["slug"] + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game:
            return
        game_config = LutrisConfig(game_config_id=bnet_game["configpath"]).game_level
        game_config["game"]["args"] = '--exec="launch %s"' % game.ngdp
        configpath = write_game_config(lutris_game_id, game_config)
        slug = service_game["slug"]
        add_game(
            name=service_game["name"],
            runner=bnet_game["runner"],
            slug=slug,
            directory=bnet_game["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=app_id,
            platform="Windows",
        )
        return slug

    def get_installed_slug(self, db_game):
        return db_game["slug"]

    def generate_installer(self, db_game, bnet_db_game):
        bnet_app = Game(bnet_db_game["id"])
        bnet_exe = bnet_app.config.game_config["exe"]
        if not os.path.isabs(bnet_exe):
            bnet_exe = os.path.join(bnet_app.config.game_config["prefix"], bnet_exe)
        return {
            "name": db_game["name"],
            "version": self.name,
            "slug": db_game["slug"] + "-" + self.id,
            "game_slug": self.get_installed_slug(db_game),
            "runner": self.get_installed_runner_name(db_game),
            "appid": db_game["appid"],
            "script": {
                "requires": self.client_installer,
                "game": {
                    "args": '--exec="launch %s"' % db_game["appid"],
                },
                "installer": [
                    {
                        "task": {
                            "name": "wineexec",
                            "executable": bnet_exe,
                            "args": '--exec="install %s"' % db_game["appid"],
                            "prefix": bnet_app.config.game_config["prefix"],
                            "description": (
                                "Battle.net will now open. Please launch "
                                "the installation of %s then close Battle.net "
                                "once the game has been downloaded." % db_game["name"]
                            ),
                        }
                    }
                ],
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def install(self, db_game):
        bnet_game = get_game_by_field(self.client_installer, "slug")
        application = Gio.Application.get_default()
        application.show_installer_window(
            [self.generate_installer(db_game, bnet_game)], service=self, appid=db_game["appid"]
        )


class BlizzardProductDbParser:
    # Adapted from DatabaseParser in https://github.com/bartok765/galaxy_blizzard_plugin
    NOT_GAMES = ("bna", "agent")
    PRODUCT_DB_PATH = "/drive_c/ProgramData/Battle.net/Agent/product.db"

    def __init__(self, prefix_path):
        self.data = self.load_product_db(prefix_path + self.PRODUCT_DB_PATH)
        self.products = {}
        self._region = ""
        self.parse()

    @property
    def region(self):
        return self._region

    @staticmethod
    def load_product_db(product_db_path):
        with open(product_db_path, "rb") as f:
            pdb = f.read()
        return pdb

    @property
    def games(self):
        if self.products:
            return [v for k, v in self.products.items() if k not in self.NOT_GAMES]
        return []

    def parse(self):
        self.products = {}
        database = ProductDb()
        database.ParseFromString(self.data)

        for product_install in database.product_installs:  # pylint: disable=no-member
            # process region
            if product_install.product_code in ["agent", "bna"] and not self.region:
                self._region = product_install.settings.play_region

            ngdp_code = product_install.product_code
            uninstall_tag = product_install.uid
            install_path = product_install.settings.install_path
            playable = product_install.cached_product_state.base_product_state.playable
            version = product_install.cached_product_state.base_product_state.current_version_str
            installed = product_install.cached_product_state.base_product_state.installed

            self.products[ngdp_code] = ProductDbInfo(
                uninstall_tag, ngdp_code, install_path, version, playable, installed
            )
