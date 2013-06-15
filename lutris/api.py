import os
import json
import urllib
import urllib2
from lutris import settings


def connect(username, password):
    credentials = urllib.urlencode({'username': username,
                                    'password': password})
    login_url = settings.SITE_URL + "user/auth/"
    request = urllib2.urlopen(login_url, credentials, 3)
    response = json.loads(request.read())
    if 'token' in response:
        token = response['token']
        token_file_path = os.path.join(settings.CACHE_DIR, 'auth-token')
        with open(token_file_path, "w") as token_file:
            token_file.write(token)
        return response['token']
    return False
