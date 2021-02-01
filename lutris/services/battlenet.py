"""Battle.net service.
Not ready yet.
"""
from gettext import gettext as _

from lutris.services.base import OnlineService


class BattleNetService(OnlineService):
    """Service class for Battle.net"""

    id = "battlenet"
    name = _("Battle.net")
    icon = "battlenet"
    medias = {}
    region = "na"

    @property
    def oauth_url(self):
        """Return the URL used for OAuth sign in"""
        if self.region == 'cn':
            return "https://www.battlenet.com.cn/oauth"
        return f"https://{self.region}.battle.net/oauth"

    @property
    def api_url(self):
        """Main API endpoint"""
        if self.region == 'cn':
            return "https://gateway.battlenet.com.cn"
        return f"https://{self.region}.api.blizzard.com"

    @property
    def login_url(self):
        """Battle.net login URL"""
        if self.region == 'cn':
            return 'https://www.battlenet.com.cn/login/zh'
        else:
            return f'https://{self.region}.battle.net/login/en'
