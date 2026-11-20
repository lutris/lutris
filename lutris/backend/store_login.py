"""Keep host-browser login handoffs and credentials inside the backend."""

import asyncio
import json
import os
from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from lutris.exceptions import LutrisError
from lutris.services import SERVICES
from lutris.services.amazon import AmazonService
from lutris.services.base import OnlineService
from lutris.services.ea_app import EAAppService
from lutris.services.egs import EpicGamesStoreService
from lutris.services.gog import GOGService
from lutris.services.itchio import ItchIoService
from lutris.services.steamfamily import SteamFamilyService
from lutris.services.ubisoft import UbisoftConnectService
from lutris.services.zoom import ZoomService
from lutris.util.cookies import WebkitCookieJar
from lutris.util.log import logger

type LoginInput = Literal["redirect", "gog", "epic", "api_key", "cookies", "ubisoft"]

_REDIRECTS = {
    "gog": (("https://embed.gog.com/on_login_success", "https://www.gog.com/on_login_success"), "code"),
    "amazon": (("https://www.amazon.com/", "https://amazon.com/"), "openid.oa2.authorization_code"),
    "zoomplatform": (("https://www.zoom-platform.com/account",), "li_token"),
}
_COOKIE_DOMAINS = {
    "gog": "gog.com",
    "humblebundle": "humblebundle.com",
    "ea_app": "ea.com",
    "steamfamily": "steampowered.com",
    "gamejolt": "gamejolt.com",
    "dlsite": "dlsite.com",
}


@dataclass(frozen=True)
class BrowserLogin:
    id: str
    name: str
    url: str
    input_kind: LoginInput


@dataclass
class _PendingLogin:
    request: BrowserLogin
    service: OnlineService
    service_id: str
    working: bool = False


_pending: dict[str, _PendingLogin] = {}


def login_input(service_id: str) -> LoginInput | None:
    if service_id == "gog":
        return "gog"
    if service_id in _REDIRECTS:
        return "redirect"
    if service_id in _COOKIE_DOMAINS:
        return "cookies"
    if service_id == "egs":
        return "epic"
    if service_id == "itchio":
        return "api_key"
    if service_id == "ubisoft":
        return "ubisoft"
    return None


async def begin(service_id: str) -> BrowserLogin:
    """Create a sign-in request. Keep its store instance for the callback."""
    input_kind = login_input(service_id)
    service_class = SERVICES.get(service_id)
    if not input_kind or not service_class or not issubclass(service_class, OnlineService):
        raise LutrisError(_("Browser sign-in is unavailable for this store."))
    if any(item.service_id == service_id for item in _pending.values()):
        raise LutrisError(_("A sign-in for this store is already open."))

    service = service_class()
    url = "https://itch.io/user/settings/api-keys" if input_kind == "api_key" else str(service.login_url)
    request = BrowserLogin(uuid4().hex, str(service.name), url, input_kind)
    _pending[request.id] = _PendingLogin(request, service, service_id)
    return request


async def cancel(request_id: str) -> None:
    pending = _pending.get(request_id)
    if pending and not pending.working:
        _pending.pop(request_id)


async def finish(request_id: str, value: str, cookie_file: str = "") -> None:
    """Validate and exchange the user's sign-in response without logging it."""
    pending = _pending.get(request_id)
    if not pending or pending.working:
        raise LutrisError(_("This sign-in request is no longer available."))
    pending.working = True
    try:
        task = asyncio.create_task(asyncio.to_thread(_finish, pending, value.strip(), cookie_file))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                _pending.pop(request_id, None)
            raise
    finally:
        pending.working = False
    _pending.pop(request_id, None)


def _finish(pending: _PendingLogin, value: str, cookie_file: str) -> None:
    service = pending.service
    if not value or len(value) > 16384:
        raise LutrisError(_("Enter the sign-in response from your browser."))
    if pending.request.input_kind in ("redirect", "gog"):
        value = _redirect_response(pending.service_id, value)
    elif pending.request.input_kind == "epic":
        value = _epic_code(value)
    elif pending.request.input_kind == "api_key" and any(character.isspace() for character in value):
        raise LutrisError(_("Enter a single API key from itch.io."))

    try:
        service.is_login_in_progress = False
        if pending.request.input_kind == "cookies":
            _import_cookies(service, Path(value), _COOKIE_DOMAINS[pending.service_id])
        elif pending.request.input_kind == "gog":
            _import_cookies(service, Path(cookie_file), _COOKIE_DOMAINS[pending.service_id], gog_redirect=value)
        elif isinstance(service, EpicGamesStoreService):
            service.start_session(authorization_code=value)
        elif isinstance(service, ItchIoService):
            if not service.validate_api_key(value):
                raise LutrisError(_("itch.io did not accept that API key."))
            service.save_api_key(value)
        elif isinstance(service, AmazonService | ZoomService):
            service.login_callback(value)
        elif isinstance(service, UbisoftConnectService):
            service.import_browser_session(_ubisoft_session(value))
        if not service.is_authenticated():
            raise LutrisError(_("The store did not accept the sign-in response."))
    except LutrisError:
        raise
    except Exception as error:
        logger.warning("Browser sign-in failed for %s (%s)", service.id, type(error).__name__)
        raise LutrisError(_("The store did not accept the sign-in response. Open the browser and try again.")) from None


def _ubisoft_session(value: str) -> dict[str, str]:
    try:
        payload = json.loads(value)
    except ValueError:
        payload = None
    session: dict[str, str] = {}
    for entry in payload if isinstance(payload, list) else [payload]:
        if not isinstance(entry, dict):
            continue
        for key in ("ticket", "sessionId", "userId", "rememberMeTicket"):
            candidate = entry.get(key)
            if isinstance(candidate, str) and candidate and candidate.isascii() and candidate.isprintable():
                if not any(character.isspace() for character in candidate):
                    session[key] = candidate
        name = entry.get("nameOnPlatform")
        if isinstance(name, str) and name.isprintable():
            session["username"] = name
    if not {"ticket", "sessionId", "userId"} <= session.keys():
        raise LutrisError(_("Paste the Ubisoft Connect login data as JSON."))
    return session


def _redirect_response(service_id: str, value: str) -> str:
    targets, key = _REDIRECTS[service_id]
    try:
        url = urlsplit(value)
        target = f"{url.scheme}://{url.netloc.lower()}{url.path or '/'}"
        parameters = parse_qs(url.query)
        response = parameters.get(key, [])
        if target in targets and len(response) == 1 and not any(char.isspace() for char in response[0]):
            return f"{target}?{urlencode({key: response[0]})}"
    except ValueError:
        pass
    raise LutrisError(_("Paste the full sign-in redirect URL from the store."))


def _epic_code(value: str) -> str:
    code = value
    if value.startswith("{"):
        try:
            payload = json.loads(value)
            code = payload.get("authorizationCode", "")
        except ValueError:
            code = ""
    if isinstance(code, str) and code.isascii() and code.replace("-", "").replace("_", "").isalnum():
        return code
    raise LutrisError(_("Paste the authorization code or the JSON shown by Epic Games."))


def _import_cookies(service: OnlineService, source: Path, domain: str, *, gog_redirect: str = "") -> None:
    try:
        if not source.is_file() or source.stat().st_size > 2_000_000:
            raise ValueError("Not a small cookie file")
        cookies = WebkitCookieJar(str(source))
        cookies.load(ignore_discard=True)
    except OSError, ValueError:
        raise LutrisError(_("Select a Netscape-format cookies.txt export from the browser.")) from None

    selected = WebkitCookieJar()
    for cookie in cookies:
        cookie_domain = cookie.domain.lstrip(".").lower()
        if cookie_domain == domain or cookie_domain.endswith(f".{domain}"):
            selected.set_cookie(cookie)
    if not len(selected):
        raise LutrisError(_("The file has no current cookies for %s.") % domain)

    if not isinstance(service.cookies_path, str):
        raise LutrisError(_("This store does not accept a cookie file."))
    target = Path(service.cookies_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as folder:
        staged = Path(folder) / "cookies.txt"
        selected.save(str(staged), ignore_discard=True)
        staged.chmod(0o600)
        service.cookies_path = str(staged)
        try:
            if isinstance(service, EAAppService | SteamFamilyService):
                service.fetch_access_token()
            elif isinstance(service, GOGService):
                service.login_callback(gog_redirect)
                if not service.is_authenticated():
                    raise LutrisError(_("GOG did not accept the sign-in response."))
            elif not service.is_connected():
                raise LutrisError(_("The store did not accept those cookies. Sign in again and export new cookies."))
        finally:
            service.cookies_path = str(target)
        os.replace(staged, target)
