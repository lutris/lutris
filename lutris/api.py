import os
import json
import urllib
import urllib2

from lutris.util.log import logger
from lutris import settings

TOKEN_FILE_PATH = os.path.join(settings.CACHE_DIR, 'auth-token')


def read_token():
    if not os.path.exists(TOKEN_FILE_PATH):
        return
    with open(TOKEN_FILE_PATH, 'r') as token_file:
        token = token_file.read()
    return token


def check_token():
    token = read_token()
    if not token:
        return False
    check_token_url = settings.SITE_URL + "user/verify/"
    token_params = urllib.urlencode({'token': token})
    request = urllib2.urlopen(check_token_url, token_params, 3)
    response = json.loads(request.read())
    if 'username' in response:
        return response['username']
    return False


def connect(username, password):
    credentials = urllib.urlencode({'username': username,
                                    'password': password})
    login_url = settings.SITE_URL + "user/auth/"
    request = urllib2.urlopen(login_url, credentials, 3)
    response = json.loads(request.read())
    if 'token' in response:
        token = response['token']
        with open(TOKEN_FILE_PATH, "w") as token_file:
            token_file.write(token)
        return response['token']
    return False


def get_library(*args):
    username = check_token()
    if not username:
        return
    logger.debug("Getting %s's library" % username)
    #library_url = settings.SITE_URL + "games/library/"
