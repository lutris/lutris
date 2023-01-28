import dataclasses as dc
import json
from typing import List, Optional

import requests


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dc.is_dataclass(o):
            return dc.asdict(o)
        return super().default(o)


@dc.dataclass
class WebsiteAuthData(object):
    cookie_jar: requests.cookies.RequestsCookieJar
    access_token: str
    region: str


@dc.dataclass(frozen=True)
class BlizzardGame:
    uid: str
    name: str
    family: str


@dc.dataclass(frozen=True)
class ClassicGame(BlizzardGame):
    registry_path: Optional[str] = None
    registry_installation_key: Optional[str] = None
    exe: Optional[str] = None
    bundle_id: Optional[str] = None


@dc.dataclass
class RegionalGameInfo:
    uid: str
    try_for_free: bool


@dc.dataclass
class ConfigGameInfo(object):
    uid: str
    uninstall_tag: Optional[str]
    last_played: Optional[str]


@dc.dataclass
class ProductDbInfo(object):
    uninstall_tag: str
    ngdp: str = ''
    install_path: str = ''
    version: str = ''
    playable: bool = False
    installed: bool = False


class Singleton(type):
    _instances = {}  # type: ignore

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class _Blizzard(object, metaclass=Singleton):
    TITLE_ID_MAP = {
        21297: RegionalGameInfo('s1', True),
        21298: RegionalGameInfo('s2', True),
        5730135: RegionalGameInfo('wow', True),
        5272175: RegionalGameInfo('prometheus', False),
        22323: RegionalGameInfo('w3', False),
        1146311730: RegionalGameInfo('destiny2', False),
        1465140039: RegionalGameInfo('hs_beta', True),
        1214607983: RegionalGameInfo('heroes', True),
        17459: RegionalGameInfo('diablo3', True),
        1447645266: RegionalGameInfo('viper', False),
        1329875278: RegionalGameInfo('odin', True),
        1279351378: RegionalGameInfo('lazarus', False),
        1514493267: RegionalGameInfo('zeus', False),
        1381257807: RegionalGameInfo('rtro', False),
        1464615513: RegionalGameInfo('wlby', False),
        5198665: RegionalGameInfo('osi', False),
        1179603525: RegionalGameInfo('fore', False)
    }
    TITLE_ID_MAP_CN = {
        **TITLE_ID_MAP,
        17459: RegionalGameInfo('d3cn', False)
    }
    BATTLENET_GAMES = [
        BlizzardGame('s1', 'StarCraft', 'S1'),
        BlizzardGame('s2', 'StarCraft II', 'S2'),
        BlizzardGame('wow', 'World of Warcraft', 'WoW'),
        BlizzardGame('wow_classic', 'World of Warcraft Classic', 'WoW_wow_classic'),
        BlizzardGame('prometheus', 'Overwatch', 'Pro'),
        BlizzardGame('w3', 'Warcraft III', 'W3'),
        BlizzardGame('hs_beta', 'Hearthstone', 'WTCG'),
        BlizzardGame('heroes', 'Heroes of the Storm', 'Hero'),
        BlizzardGame('d3cn', '暗黑破壞神III', 'D3CN'),
        BlizzardGame('diablo3', 'Diablo III', 'D3'),
        BlizzardGame('viper', 'Call of Duty: Black Ops 4', 'VIPR'),
        BlizzardGame('odin', 'Call of Duty: Modern Warfare', 'ODIN'),
        BlizzardGame('lazarus', 'Call of Duty: MW2 Campaign Remastered', 'LAZR'),
        BlizzardGame('zeus', 'Call of Duty: Black Ops Cold War', 'ZEUS'),
        BlizzardGame('rtro', 'Blizzard Arcade Collection', 'RTRO'),
        BlizzardGame('wlby', 'Crash Bandicoot 4: It\'s About Time', 'WLBY'),
        BlizzardGame('osi', 'Diablo® II: Resurrected', 'OSI'),
        BlizzardGame('fore', 'Call of Duty: Vanguard', 'FORE')
    ]
    CLASSIC_GAMES = [
        ClassicGame('d2', 'Diablo® II', 'Diablo II', 'Diablo II', 'DisplayIcon', "Game.exe", "com.blizzard.diabloii"),
        ClassicGame('d2LOD', 'Diablo® II: Lord of Destruction®', 'Diablo II'),  # TODO exe and bundleid
        ClassicGame('w3ROC', 'Warcraft® III: Reign of Chaos', 'Warcraft III', 'Warcraft III',
                    'InstallLocation', 'Warcraft III.exe', 'com.blizzard.WarcraftIII'),
        ClassicGame('w3tft', 'Warcraft® III: The Frozen Throne®', 'Warcraft III', 'Warcraft III',
                    'InstallLocation', 'Warcraft III.exe', 'com.blizzard.WarcraftIII'),
        ClassicGame('sca', 'StarCraft® Anthology', 'Starcraft', 'StarCraft')  # TODO exe and bundleid
    ]

    def __init__(self):
        self._games = {game.uid: game for game in self.BATTLENET_GAMES + self.CLASSIC_GAMES}

    def __getitem__(self, key: str) -> BlizzardGame:
        """
        :param key: str uid (eg. "prometheus")
        :returns: game by `key`
        """
        return self._games[key]

    def game_by_title_id(self, title_id: int, cn: bool) -> BlizzardGame:
        """
        :param cn: flag if china game definitions should be search though
        :raises KeyError: when unknown title_id for given region
        """
        if cn:
            regional_info = self.TITLE_ID_MAP_CN[title_id]
        else:
            regional_info = self.TITLE_ID_MAP[title_id]
        return self[regional_info.uid]

    def try_for_free_games(self, cn: bool) -> List[BlizzardGame]:
        """
        :param cn: flag if china game definitions should be search though
        """
        return [
            self[info.uid] for info
            in (self.TITLE_ID_MAP_CN if cn else self.TITLE_ID_MAP).values()
            if info.try_for_free
        ]


Blizzard = _Blizzard()
