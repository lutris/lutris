"""Battle.net service.
Not ready yet.
"""
import pickle
from gettext import gettext as _
from urllib.parse import parse_qs, urlparse

import requests

from lutris.services.base import OnlineService
from lutris.util.log import logger

CLIENT_ID = "6cb41a854631426c8a74d4084c4d61f2"
CLIENT_SECRET = "FFwxmMBGtEqPydyi9FMhj1zIvlJrBTE1"
REDIRECT_URI = "https://lutris.net"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"


class InvalidCredentials(Exception):
    pass


def _found_region(cookies):
    try:
        for cookie in cookies:
            if cookie['name'] == 'JSESSIONID':
                _region = cookie['domain'].split('.')[0]
                # 4th region - chinese uses different endpoints, not covered by current plugin
                if _region.lower() in ['eu', 'us', 'kr']:
                    return _region
                raise ValueError(f'Unknown region {_region}')
        raise ValueError('JSESSIONID cookie not found')
    except Exception:
        return 'eu'


def guess_region(local_client):
    """
    1. read the consts.py
    2. try read the battlenet db OR config get the region info.
    3. try query https://www.blizzard.com/en-us/user
    4. failed return ""
    """
    try:
        if local_client._load_local_files():
            if local_client.config_parser.region:
                return local_client.config_parser.region.lower()

            if local_client.database_parser.region:
                return local_client.database_parser.region.lower()

        response = requests.get('https://www.blizzard.com/en-us/user', timeout=10)
        assert response.status_code == 200
        return response.json()['region'].lower()
    except Exception as e:
        logger.error('%s', e)
        return ""


class BattleNetClient():
    def __init__(self, plugin):
        self._plugin = plugin
        self.user_details = None
        self._region = None
        self.session = None
        self.creds = None
        self.timeout = 40.0
        self.attempted_to_set_battle_tag = None
        self.auth_data = {}

    def is_authenticated(self):
        return self.session is not None

    def shutdown(self):
        if self.session:
            self.session.close()
            self.session = None

    def process_stored_credentials(self, stored_credentials):
        auth_data = {
            "cookie_jar": pickle.loads(bytes.fromhex(stored_credentials['cookie_jar'])),
            "access_token": stored_credentials['access_token'],
            "region": stored_credentials['region'] if 'region' in stored_credentials else 'eu'
        }

        # set default user_details data from cache
        if 'user_details_cache' in stored_credentials:
            self.user_details = stored_credentials['user_details_cache']
            self.auth_data = auth_data
        return auth_data

    def get_auth_data_login(self, cookie_jar, credentials):
        code = parse_qs(urlparse(credentials['end_uri']).query)["code"][0]

        s = requests.Session()
        url = f"{self.blizzard_oauth_url}/token"
        data = {
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code
        }
        response = s.post(url, data=data)
        response.raise_for_status()
        result = response.json()
        access_token = result["access_token"]
        self.auth_data = {"cookie_jar": cookie_jar, "access_token": access_token, "region": self.region}
        return self.auth_data

    # NOTE: use user data to present usertag/name to Galaxy, if this token expires and plugin cannot refresh it
    # use stored usertag/name if token validation fails, this is temporary solution, as we do not need that
    # endpoint for nothing else at this moment
    def validate_auth_status(self, auth_status):
        if 'error' in auth_status:
            if not self.user_details:
                raise InvalidCredentials()
            return False
        if not self.user_details:
            raise InvalidCredentials()
        if not ("authorities" in auth_status and "IS_AUTHENTICATED_FULLY" in auth_status["authorities"]):
            raise InvalidCredentials()
        return True

    def parse_user_details(self):
        if 'battletag' in self.user_details and 'id' in self.user_details:
            return (self.user_details["id"], self.user_details["battletag"])
        raise InvalidCredentials()

    def authenticate_using_login(self):
        _URI = (
            f'{self.blizzard_oauth_url}/authorize?response_type=code&'
            f'client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=wow.profile+sc2.profile'
        )
        return {
            "window_title": "Login to Battle.net",
            "window_width": 540,
            "window_height": 700,
            "start_uri": _URI,
            "end_uri_regex": r"(.*logout&app=oauth.*)|(^http://friendsofgalaxy\.com.*)"
        }

    def parse_auth_after_setting_battletag(self):
        self.creds["user_details_cache"] = self.user_details
        try:
            battletag = self.user_details["battletag"]
        except KeyError as ex:
            raise InvalidCredentials() from ex
        self._plugin.store_credentials(self.creds)
        return (self.user_details["id"], battletag)

    def parse_cookies(self, cookies):
        if not self.region:
            self.region = _found_region(cookies)
        new_cookies = {cookie["name"]: cookie["value"] for cookie in cookies}
        return requests.cookies.cookiejar_from_dict(new_cookies)

    def set_credentials(self):
        self.creds = {
            "cookie_jar": pickle.dumps(self.auth_data["cookie_jar"]).hex(),
            "access_token": self.auth_data["access_token"],
            "user_details_cache": self.user_details,
            "region": self.auth_data["region"]
        }

    def parse_battletag(self):
        try:
            battletag = self.user_details["battletag"]
        except KeyError:
            st_parameter = requests.utils.dict_from_cookiejar(self.auth_data["cookie_jar"])["BA-tassadar"]
            start_uri = f'{self.blizzard_battlenet_login_url}/flow/' \
                f'app.app?step=login&ST={st_parameter}&app=app&cr=true'
            auth_params = {
                "window_title": "Login to Battle.net",
                "window_width": 540,
                "window_height": 700,
                "start_uri": start_uri,
                "end_uri_regex": r".*accountName.*"
            }
            self.attempted_to_set_battle_tag = True
            return auth_params

        self._plugin.store_credentials(self.creds)
        return (self.user_details["id"], battletag)

    async def create_session(self):
        self.session = requests.Session()
        self.session.cookies = self.auth_data["cookie_jar"]
        self.region = self.auth_data["region"]
        self.session.max_redirects = 300
        self.session.headers = {
            "Authorization": f"Bearer {self.auth_data['access_token']}",
            "User-Agent": USER_AGENT
        }

    def refresh_credentials(self):
        creds = {
            "cookie_jar": pickle.dumps(self.session.cookies).hex(),
            "access_token": self.auth_data["access_token"],
            "region": self.auth_data["region"],
            "user_details_cache": self.user_details
        }
        self._plugin.store_credentials(creds)

    @property
    def region(self):
        if self._region is None:
            self._region = guess_region(self._plugin.local_client)
        return self._region

    @region.setter
    def region(self, value):
        self._region = value

    @property
    def blizzard_accounts_url(self):
        if self.region == 'cn':
            return "https://account.blizzardgames.cn"
        return f"https://{self.region}.account.blizzard.com"

    @property
    def blizzard_oauth_url(self):
        if self.region == 'cn':
            return "https://www.battlenet.com.cn/oauth"
        return f"https://{self.region}.battle.net/oauth"

    @property
    def blizzard_api_url(self):
        if self.region == 'cn':
            return "https://gateway.battlenet.com.cn"
        return f"https://{self.region}.api.blizzard.com"

    @property
    def blizzard_battlenet_download_url(self):
        if self.region == 'cn':
            return "https://cn.blizzard.com/zh-cn/apps/battle.net/desktop"
        return "https://www.blizzard.com/apps/battle.net/desktop"

    @property
    def blizzard_battlenet_login_url(self):
        if self.region == 'cn':
            return 'https://www.battlenet.com.cn/login/zh'
        return f'https://{self.region}.battle.net/login/en'


class BattleNetService(OnlineService):
    """Service class for Battle.net"""

    id = "battlenet"
    name = _("Battle.net")
    icon = "battlenet"
    medias = {}
