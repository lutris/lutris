"""Resolution of the proxy Lutris uses for its own network requests.

Lutris has always left proxying to the standard ``http_proxy``, ``https_proxy`` and
``no_proxy`` environment variables, which urllib and requests both honor on their own.
Desktops that keep their proxy configuration to themselves leave those unset however -
KDE Plasma writes it to ``kioslaverc``, where nothing outside KIO ever looks - so the
preferences accept a proxy directly as well.

A proxy entered in the preferences is applied by overwriting those same variables. That
looks roundabout when urllib and requests can both be handed a proxy directly, but the
environment is the only place requests consults the list of hosts to *bypass*: it applies
``no_proxy`` to the proxies it discovers in the environment and nowhere else. Going
through the environment is therefore what makes the bypass list work at all, and it has
the side benefit of covering every HTTP client in the process, plus anything Lutris runs.
"""

import os
import urllib.parse

from lutris.settings import read_setting
from lutris.util.log import logger

# The scheme assumed when the proxy is entered as a bare 'host:port'.
DEFAULT_PROXY_SCHEME = "http"

# Lutris writes the lower case names, which both urllib and requests prefer, and clears
# the upper case ones so that nothing reading either spelling can disagree about which
# proxy is in use.
PROXY_SETTING_NAMES = ("http_proxy", "https_proxy", "no_proxy")
PROXY_ENVIRONMENT_VARIABLES = tuple(name for base in PROXY_SETTING_NAMES for name in (base, base.upper()))

# The variables Lutris was started with; restored if the proxy preference is cleared.
_INHERITED_ENVIRONMENT = {name: os.environ.get(name) for name in PROXY_ENVIRONMENT_VARIABLES}


def get_proxy_url() -> str:
    """Returns the proxy configured in the preferences, with a scheme added if the user
    left one off. This is empty when no proxy has been configured."""
    proxy_url = read_setting("proxy_url").strip()
    if proxy_url and "://" not in proxy_url:
        proxy_url = f"{DEFAULT_PROXY_SCHEME}://{proxy_url}"
    return proxy_url


def get_ignored_hosts() -> str:
    """Returns the comma separated hosts that should be reached directly, as entered in
    the preferences."""
    return read_setting("proxy_ignore_hosts").strip()


def get_ignored_host_list() -> list[str]:
    """Returns the hosts that should be reached directly, as a list."""
    return [host.strip() for host in get_ignored_hosts().split(",") if host.strip()]


def apply_to_environment() -> None:
    """Applies the proxy from the preferences to this process's environment, where every
    HTTP client Lutris uses will find it. Clearing the preference puts back the variables
    Lutris was started with."""
    proxy_url = get_proxy_url()
    if proxy_url:
        wanted = {"http_proxy": proxy_url, "https_proxy": proxy_url, "no_proxy": get_ignored_hosts()}
    else:
        wanted = _INHERITED_ENVIRONMENT

    if os.environ.get("http_proxy") != wanted.get("http_proxy"):
        if proxy_url:
            logger.debug("Sending Lutris network requests through %s", redact_credentials(proxy_url))
        else:
            logger.debug("Leaving Lutris network requests to the inherited proxy configuration")

    for name in PROXY_ENVIRONMENT_VARIABLES:
        value = wanted.get(name)
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)


def redact_credentials(proxy_url: str) -> str:
    """Replaces the user name and password of a proxy URL, so that it can be logged."""
    parsed = urllib.parse.urlsplit(proxy_url)
    if not parsed.username:
        return proxy_url

    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urllib.parse.urlunsplit(parsed._replace(netloc=f"REDACTED@{netloc}"))
