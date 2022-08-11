# Ubisoft Connect client adapted from the Galaxy integration by Rasmus Luund.
# https://github.com/FriendsOfGalaxy/galaxy-integration-uplay

import json
import time
from datetime import datetime
from gettext import gettext as _

import requests

from lutris.util.log import logger
from lutris.util.ubisoft.consts import CHROME_USERAGENT, CLUB_APPID, UBISOFT_APPID


def parse_date(date_str):
    date_example = "2022-01-25T05:44:59.192453"
    return datetime.strptime(date_str[:len(date_example)], "%Y-%m-%dT%H:%M:%S.%f")


class UbisoftConnectClient():
    def __init__(self, service):
        self._service = service
        self._auth_lost_callback = None
        self.token = None
        self.session_id = None
        self.refresh_token = None
        self.refresh_time = None
        self.user_id = None
        self.user_name = None
        self.__refresh_in_progress = False
        self._session = requests.session()
        self._session.headers.update({
            'Authorization': None,
            'Ubi-AppId': CLUB_APPID,
            "User-Agent": CHROME_USERAGENT,
            'Ubi-SessionId': None
        })

    def close(self):
        # If closing is attempted while plugin is inside refresh workflow then give it a chance to finish it.
        if self.__refresh_in_progress:
            time.sleep(1.5)
        self._session.close()

    def request(self, method, url, *args, **kwargs):
        try:
            return self._session.request(method, url, *args, **kwargs)
        except Exception as ex:
            logger.exception(ex)

    def set_auth_lost_callback(self, callback):
        self._auth_lost_callback = callback

    def is_authenticated(self):
        return self.token is not None

    def _do_request(self, method, *args, **kwargs):
        if not kwargs or 'headers' not in kwargs:
            logger.info("No headers in kwargs, using session headers")
            kwargs['headers'] = self._session.headers
        if 'add_to_headers' in kwargs:
            for header in kwargs['add_to_headers']:
                kwargs['headers'][header] = kwargs['add_to_headers'][header]
            kwargs.pop('add_to_headers')

        response = self.request(method, *args, **kwargs)
        logger.info("Response status: %s", response)
        result = response.json()
        if 'errorCode' in result and 'message' in result:
            raise RuntimeError(result['message'])
        return result

    def _do_request_safe(self, method, *args, **kwargs):
        result = {}
        try:
            refresh_needed = False
            if self.refresh_token:
                logger.debug('rememberMeTicket expiration time: %s', self.refresh_time)
                refresh_needed = (
                    self.refresh_time is None
                    or datetime.now() > datetime.fromtimestamp(int(self.refresh_time))
                )
            if refresh_needed:
                self._refresh_auth()
                result = self._do_request(method, *args, **kwargs)
            else:
                try:
                    result = self._do_request(method, *args, **kwargs)
                except Exception:
                    # fallback for another reason than expired time or wrong calculation due to changing time zones
                    logger.debug('Fallback refresh')
                    if not self.refresh_token:
                        logger.warning(
                            "No refresh token present, possibly unchecked remember me when connecting plugin"
                        )
                    self._refresh_auth()
                    result = self._do_request(method, *args, **kwargs)
        except Exception as ex:
            logger.error("Unable to refresh authentication calling auth lost: %s", ex)
            if self._auth_lost_callback:
                self._auth_lost_callback()
            raise RuntimeError(_("Ubisoft authentication has been lost: %s") % ex) from ex
        return result

    def _do_options_request(self):
        self._do_request('options', "https://public-ubiservices.ubi.com/v3/profiles/sessions", headers={
            "Origin": "https://connect.ubisoft.com",
            "Referer": f"https://connect.ubisoft.com/login?appId={UBISOFT_APPID}",
            "User-Agent": CHROME_USERAGENT,
        })

    def _refresh_auth(self):
        if self.__refresh_in_progress:
            logger.info('Refreshing already in progress.')
            while self.__refresh_in_progress:
                time.sleep(0.2)
        else:
            self.__refresh_in_progress = True
            try:
                self._refresh_ticket()
                self._service.store_credentials(self.get_credentials())
            except:
                self._refresh_remember_me()
                self._refresh_ticket()
                self._service.store_credentials(self.get_credentials())
            finally:
                self.__refresh_in_progress = False

    def _refresh_remember_me(self):
        logger.debug('Refreshing rememberMeTicket')
        self._do_options_request()
        j = self._do_request(
            'post',
            'https://public-ubiservices.ubi.com/v3/profiles/sessions',
            headers={
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US;en;q=0.5',
                'Authorization': f"rm_v1 t={self.refresh_token}",
                'Content-Type': 'application/json',
                'Ubi-AppId': CLUB_APPID,
                'User-Agent': CHROME_USERAGENT,
                'Host': 'public-ubiservices.ubi.com',
                'Origin': 'https://connect.ubisoft.com',
                'Referer': 'https://connect.ubisoft.com',
            },
            json={"rememberMe": True}
        )
        self._handle_authorization_response(j)

    def _refresh_ticket(self):
        logger.debug('Refreshing ticket')
        self._do_options_request()
        j = self._do_request(
            'put',
            'https://public-ubiservices.ubi.com/v3/profiles/sessions',
            headers={
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US;en;q=0.5',
                'Authorization': f"Ubi_v1 t={self.token}",
                'Content-Type': 'application/json',
                'Ubi-AppId': CLUB_APPID,
                'User-Agent': CHROME_USERAGENT,
                'Host': 'public-ubiservices.ubi.com',
                'Origin': 'https://connect.ubisoft.com',
                'Referer': 'https://connect.ubisoft.com',
            })
        self._handle_authorization_response(j)

    def _handle_authorization_response(self, j):
        if 'expiration' in j and 'serverTime' in j:
            refresh_time = datetime.now() + (parse_date(j['expiration']) - parse_date(j['serverTime']))
            j['refreshTime'] = round(refresh_time.timestamp())
            self.restore_credentials(j)

    def restore_credentials(self, data):
        self.token = data['ticket']
        self.session_id = data['sessionId']
        self.user_id = data['userId']
        if data.get('username'):
            self.user_name = data['username']
        self.refresh_time = data.get('refreshTime', '0')
        if data.get('rememberMeTicket'):
            self.refresh_token = data['rememberMeTicket']

        self._session.headers.update({
            "Authorization": f"Ubi_v1 t={self.token}",
            "Ubi-SessionId": self.session_id
        })

    def get_credentials(self):
        creds = {
            "ticket": self.token,
            "sessionId": self.session_id,
            "rememberMeTicket": self.refresh_token,
            "userId": self.user_id,
            "refreshTime": self.refresh_time
        }

        if self.user_name:
            creds["username"] = self.user_name

        return creds

    def authorise_with_stored_credentials(self, credentials):
        self.restore_credentials(credentials)
        if not self.user_name or not self.user_id:
            user_data = self.get_user_data()
        else:
            user_data = {"username": self.user_name,
                         "userId": self.user_id}
        self.post_sessions()
        self._service.store_credentials(self.get_credentials())
        return user_data

    def authorise_with_local_storage(self, storage_jsons):
        user_data = {}
        tasty_storage_values = ['userId', 'nameOnPlatform', 'ticket', 'rememberMeTicket', 'sessionId']
        for json_ in storage_jsons:
            for key in json_:
                if key in tasty_storage_values:
                    user_data[key] = json_[key]

        user_data['userId'] = user_data.pop('userId')
        user_data['username'] = user_data.pop('nameOnPlatform')

        self.restore_credentials(user_data)
        self.post_sessions()
        self._service.store_credentials(self.get_credentials())
        return user_data

    # Deprecated 0.39
    def get_user_data(self):
        return self._do_request_safe('get', f"https://public-ubiservices.ubi.com/v3/users/{self.user_id}")

    def get_friends(self):
        return self._do_request_safe('get', 'https://api-ubiservices.ubi.com/v2/profiles/me/friends')

    def get_club_titles(self):
        payload = {
            "operationName": "AllGames",
            "variables": {"owned": True},
            "query": "query AllGames {"
                     "viewer {"
                     "    id"
                     "    ...ownedGamesList"
                     "  }"
                     "}"
                     "fragment gameProps on Game {"
                     "  id"
                     "  spaceId"
                     "  name"
                     "}"
                     "fragment ownedGameProps on Game {"
                     "  ...gameProps"
                     "  viewer {"
                     "    meta {"
                     "      id"
                     "      ownedPlatformGroups {"
                     "        id"
                     "        name"
                     "        type"
                     "      }"
                     "    }"
                     "  }"
                     "}"
                     "fragment ownedGamesList on User {"
                     "  ownedGames: games(filterBy: {isOwned: true}) {"
                     "    totalCount"
                     "    nodes {"
                     "      ...ownedGameProps"
                     "    }"
                     "  }"
                     "}"
        }
        payload = json.dumps(payload)
        headers = {'Content-Type': 'application/json'}
        return self._do_request_safe(
            'post',
            "https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql",
            add_to_headers=headers,
            data=payload
        )

    def get_game_stats(self, space_id):
        url = f"https://public-ubiservices.ubi.com/v1/profiles/{self.user_id}/statscard?spaceId={space_id}"
        headers = {
            'Ubi-RequestedPlatformType': "uplay",
            'Ubi-LocaleCode': "en-GB"
        }
        try:
            return self._do_request('get', url, add_to_headers=headers)
        except Exception as ex:  # 412: no stats available for this user
            logger.debug(ex)
            return {}

    def get_applications(self, spaces):
        space_string = ','.join(space['spaceId'] for space in spaces)
        return self._do_request_safe(
            'get',
            f"https://api-ubiservices.ubi.com/v2/applications?spaceIds={space_string}"
        )

    def get_configuration(self):
        response = self._do_request_safe('get', 'https://uplaywebcenter.ubi.com/v1/configuration')
        return response.json()

    def post_sessions(self):
        headers = {'Content-Type': 'application/json'}
        return self._do_request_safe(
            'post',
            "https://public-ubiservices.ubi.com/v2/profiles/sessions",
            add_to_headers=headers
        )

    def get_subscription(self):
        try:
            sub_games = self._do_request('get', "https://api-uplayplusvault.ubi.com/v1/games")
        except Exception:
            logger.info("Uplay plus Subscription not active")
            return None
        return sub_games

    def activate_game(self, activation_id):
        response = self._do_request_safe(
            'post',
            f"https://api-uplayplusvault.ubi.com/v1/games/activate/{activation_id}"
        )
        return 'games' in response
