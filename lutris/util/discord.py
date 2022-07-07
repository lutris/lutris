import base64
import json

import requests


def set_discord_status(token, status):
    """Set a custom status for a user referenced by its token"""
    if not token:
        return
    payload = json.dumps({"custom_status": {"text": status}})
    super_properties_raw = (
        '{"os":"Linux","browser":"Firefox","device":"","system_locale":"en-US",'
        '"browser_user_agent":"Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0",'
        '"browser_version":"102.0","os_version":"","referrer":"","referring_domain":"",'
        '"referrer_current":"","referring_domain_current":"","release_channel":"stable",'
        '"client_build_number":135341,"client_event_source":null}'
    )
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US",
        "Alt-Used": "discord.com",
        "Authorization": token,
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": str(len(payload)),
        "Content-Type": "application/json",
        "Host": "discord.com",
        "Origin": "https://discord.com",
        "Pragma": "no-cache",
        "Referer": "",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0",
        "X-Debug-Options": "bugReporterEnabled",
        "X-Discord-Locale": "en-US",
        "X-Super-Properties": base64.b64encode(super_properties_raw.encode('utf-8'))
    }
    return requests.patch("https://discord.com/api/v9/users/@me/settings", payload, headers=headers)
