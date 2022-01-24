# pylint: disable=line-too-long
import os
import re

UBISOFT_REGISTRY = "SOFTWARE\\Ubisoft"
STEAM_REGISTRY = "Software\\Valve\\Steam"
UBISOFT_REGISTRY_LAUNCHER = "SOFTWARE\\Ubisoft\\Launcher"
UBISOFT_REGISTRY_LAUNCHER_INSTALLS = "SOFTWARE\\Ubisoft\\Launcher\\Installs"

UBISOFT_SETTINGS_YAML = os.path.join(os.getenv('LOCALAPPDATA'), 'Ubisoft Game Launcher', 'settings.yml')

UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES = ["gamename", "l1", '', 'ubisoft game', 'name']

CHROME_USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/72.0.3626.121 Safari/537.36"
)
CLUB_APPID = "b8fde481-327d-4031-85ce-7c10a202a700"
CLUB_GENOME_ID = "fbd6791c-a6c6-4206-a75e-77234080b87b"

AUTH_PARAMS = {
    "window_title": "Login | Ubisoft WebAuth",
    "window_width": 460,
    "window_height": 690,
    "start_uri": f"https://connect.ubisoft.com/login?appId={CLUB_APPID}&genomeId={CLUB_GENOME_ID}"
    "&lang=en-US&nextUrl=https:%2F%2Fconnect.ubisoft.com%2Fready",
    "end_uri_regex": r".*rememberMeTicket.*"
}


def regex_pattern(regex):
    return ".*" + re.escape(regex) + ".*"


AUTH_JS = {regex_pattern(r"connect.ubisoft.com/ready"): [
    r'''
            window.location.replace("https://connect.ubisoft.com/change_domain/");

            '''
],
    regex_pattern(r"connect.ubisoft.com/change_domain"): [
    r'window.location.replace(localStorage.getItem("PRODloginData") +","+ '
    r'localStorage.getItem("PRODrememberMe") +"," + localStorage.getItem("PRODlastProfile"));'
]}
