"""
The Humble Bundle API client
"""

__author__ = "Joel Pedraza"
__copyright__ = "Copyright 2014, Joel Pedraza"
__license__ = "MIT"

__all__ = ['HumbleApi', 'LOGIN_URL', 'ORDER_LIST_URL', 'CLAIMED_ENTITIES_URL',
           'SIGNED_DOWNLOAD_URL', 'STORE_URL']

from lutris.external.humblebundle.decorators import callback
from lutris.external.humblebundle.exceptions import HumbleException
from lutris.external.humblebundle import handlers

import requests
from logging import getLogger, NullHandler

ROOT_URL = 'https://www.humblebundle.com'
API_URL = ROOT_URL + '/api/v1'
LOGIN_URL = ROOT_URL + '/login'
ORDER_LIST_URL = API_URL + '/user/order'
ORDER_URL = API_URL + '/order/{order_id}'
CLAIMED_ENTITIES_URL = API_URL + '/user/claimed/entities'
SIGNED_DOWNLOAD_URL = API_URL + '/user/Download/{machine_name}/sign'
STORE_URL = ROOT_URL + '/store/api/humblebundle'


class HumbleApi(object):
    """
    The Humble Bundle API is not stateless, it stores an authentication token
    as a cookie named _simpleauth_sess

    The Requests.Session handles storing the auth token. To load some persisted
    cookies simply set session.cookies after initialization
    """

    """
    Notes:
    ======

    * The API itself is very inconsistent, for example the error syntax varies
      between API calls

    * The response should always contain valid JSON when the ajax param is set
      to true. It occasionally breaks this contract and returns no body. Grr!

    * Because of these two issues, we have separate handlers for each API call.
      See humblebundle.handlers

    """

    default_headers = {'Accept': 'application/json',
                       'Accept-Charset': 'utf-8',
                       'Keep-Alive': 'true'}
    default_params = {'ajax': 'true'}
    store_default_params = {"request": 1,
                            "page_size": 20,
                            "sort": "bestselling",
                            "page": 0,
                            "search": None}

    def __init__(self):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        self.session.params.update(self.default_params)

    """
    API call methods
    ================

    Delegate to handlers to validate response, catch and raise exceptions, and
    convert response to model

    Unimplemented:
        * https://www.humblebundle.com/signup?ajax=true
        * https://www.humblebundle.com/user/unclaimed_orders?ajax=true
        * https://www.humblebundle.com/bundle/claim?ajax=true
        * https://www.humblebundle.com/api/v1/model/(SubProduct|ModelPointer)
            - Lots of references to /v1/model/* in the claimed entities
              response, not sure what they are.
    """

    @callback
    def login(self, username, password, authy_token=None,
              recaptcha_challenge=None, recaptcha_response=None,
              *args, **kwargs):
        """
        Login to the Humble Bundle API. The response sets the _simpleauth_sess
        cookie which is stored in the session automatically.

        :param str username: The user account to authenticate with
        :param str password: The password to authenticate with
        :param authy_token: (optional) The GoogleAuthenticator/Authy token
                            (One time pass)
        :type authy_token: integer or str
        :param str recaptcha_challenge: (optional) The challenge signed by
                                       Humble Bundle's public key from reCAPTCHA
        :param str recaptcha_response: (optional) The plaintext solved CAPTCHA
        :param list args: (optional) Extra positional args to pass
                          to the request
        :param dict kwargs: (optional) Extra keyword args to pass to the
                            request. If a data dict is supplied a key collision
                            with any of the above params will resolved in favor
                            of the supplied param
        :return: A Future object encapsulating the login request
        :rtype: Future
        :raises RequestException: if the connection failed
        :raises HumbleResponseException: if the response was invalid
        :raises HumbleCredentialException: if the username and password
                                           did not match
        :raises HumbleCaptchaException: if the captcha challenge failed
        :raises HumbleTwoFactorException: if the two-factor authentication
                                          challenge failed
        :raises HumbleAuthenticationException: if some other authentication
                                               error occurred

        """

        self.logger.info("Logging in")

        default_data = {
            'username': username,
            'password': password,
            'authy-token': authy_token,
            'recaptcha_challenge_field': recaptcha_challenge,
            'recaptcha_response_field': recaptcha_response
        }
        kwargs.setdefault('data', {}).update({
            k: v for k, v in default_data.items() if v is not None
        })

        response = self._request('POST', LOGIN_URL, *args, **kwargs)
        return handlers.login_handler(self, response)

    @callback
    def get_gamekeys(self, *args, **kwargs):
        """
        Fetch all the gamekeys owned by an account.

        A gamekey is a string that uniquely identifies an order from the humble
        store.

        :param list args: (optional) Extra positional args
                          to pass to the request
        :param dict kwargs: (optional) Extra keyword args to pass to the request
        :return: A list of gamekeys
        :rtype: list
        :raises RequestException: if the connection failed
        :raises HumbleAuthenticationException: if not logged in
        :raises HumbleResponseException: if the response was invalid
        """

        self.logger.info("Downloading gamekeys")
        response = self._request('GET', ORDER_LIST_URL, *args, **kwargs)
        return handlers.gamekeys_handler(self, response)

    @callback
    def get_order(self, order_id, *args, **kwargs):
        """
        Download an order by it's id

        :param order_id: The identifier ("gamekey") that uniquely identifies
                         the order
        :param list args: (optional) Extra positional args to pass
                          to the request
        :param dict kwargs: (optional) Extra keyword args to pass to the request
        :return: The :py:class:`Order` requested
        :rtype: Order
        :raises RequestException: if the connection failed
        :raises HumbleAuthenticationException: if not logged in
        :raises HumbleResponseException: if the response was invalid
        """
        self.logger.info("Getting order %s", order_id)
        url = ORDER_URL.format(order_id=order_id)
        response = self._request('GET', url, *args, **kwargs)
        return handlers.order_handler(self, response)

    # TODO: model the claimed_entities response
    @callback
    def get_claimed_entities(self, platform=None, *args, **kwargs):
        """
        Download all the claimed entities for a user

        This call can take a long time for the server to start responding as it
        has to collect a lot of data about the user's purchases.

        This method does not parse the result into a subclass of BaseModel, but
        instead returns the decoded json.
        I'm lazy and this just isn't very useful for the client this lib was
        written for.

        :param platform:
        :param list args: (optional) Extra positional args
                          to pass to the request
        :param dict kwargs: (optional) Extra keyword args to pass to the request
        :return: The parsed json response
        :rtype: dict
        :raises RequestException: if the connection failed
        :raises HumbleAuthenticationException: if not logged in
        :raises HumbleResponseException: if the response was invalid
        """
        self.logger.info("Downloading claimed entities")

        if platform:
            supported_platforms = (
                'android', 'audio', 'ebook', 'linux', 'mac', 'windows'
            )
            if platform in supported_platforms:
                kwargs.setdefault('params', {})['platform'] = platform
            else:
                raise HumbleException(
                    "Unsupported platform: {}".format(platform)
                )

        kwargs.setdefault('timeout', 60)  # This call takes forever
        response = self._request('GET', CLAIMED_ENTITIES_URL, *args, **kwargs)
        return handlers.claimed_entities_handler(self, response)

    @callback
    def sign_download_url(self, machine_name, *args, **kwargs):
        """
        Get a download URL by specifying the machine
        name of a :py:class:`Subproduct`

        Unfortunately it always returns the first download in the download
        list. This makes it pretty useless for most platforms.

        :param machine_name:
        :param list args: (optional) Extra positional args
                          to pass to the request
        :param dict kwargs: (optional) Extra keyword args to pass to the request
        :return: The signed url
        :rtype: str
        :raises RequestException: if the connection failed
        :raises HumbleAuthenticationException: if not logged in
        :raises HumbleResponseException: if the response was invalid
        """
        self.logger.info("Signing download url for %s", machine_name)
        url = SIGNED_DOWNLOAD_URL.format(machine_name=machine_name)
        response = self._request('GET', url, *args, **kwargs)
        return handlers.sign_download_url_handler(self, response)

    @callback
    def search_store(self, search_query, *args, **kwargs):
        """
        Download a list of the results from the query.

        :param search_query:
        :param list args: (optional) Extra positional args
                          to pass to the request
        :param dict kwargs: (optional) Extra keyword args to pass to the request
        :return: The results
        :rtype: list
        :raises RequestException: if the connection failed
        :raises HumbleResponseException: if the response was invalid
        """
        self.logger.info("Searching store for url for {search_query}".format(
            search_query=search_query
        ))
        url = STORE_URL

        # setup query string parameters
        params = self.store_default_params.copy()
        params['search'] = search_query

        # make sure kwargs['params'] is a dict
        kwargs_params = kwargs.get('params', {}) if kwargs.get('params') else {}

        kwargs_params.update(params)  # pull in any params in to kwargs
        kwargs['params'] = kwargs_params

        response = self._request('GET', url, *args, **kwargs)
        # may need to loop after a while
        self.store_default_params['request'] += 1

        return handlers.store_products_handler(self, response)

    # Internal helper methods

    def _request(self, *args, **kwargs):
        """
        Set sane defaults that aren't session wide. Otherwise maintains the api
        of Session.request
        """

        kwargs.setdefault('timeout', 30)
        return self.session.request(*args, **kwargs)
