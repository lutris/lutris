"""Exercise browser handoffs without using real account credentials."""

import asyncio
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from lutris import settings
from lutris.backend import services, store_login
from lutris.exceptions import LutrisError
from lutris.services.amazon import AmazonService
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.ubisoft import UbisoftConnectService
from lutris.util.credentials import save_credentials
from lutris.util.ubisoft.client import UbisoftConnectClient


def test_gog_rejects_lookalike_origins_and_retries_the_same_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = tmp_path / ".gog.token"
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(".gog.com\tTRUE\t/\tTRUE\t0\tsession\tfixture\n", encoding="utf-8")
    responses: list[str] = []

    def exchange(self: GOGService, url: str, refresh_token: str = "") -> None:
        responses.append(url)
        save_credentials(self.token_path, "{}")

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(GOGService, "token_path", str(token))
    monkeypatch.setattr(GOGService, "cookies_path", str(tmp_path / ".gog.auth"))
    monkeypatch.setattr(GOGService, "request_token", exchange)

    async def run() -> None:
        request = await store_login.begin("gog")
        assert urlsplit(request.url).netloc == "auth.gog.com"
        for reply in (
            "https://embed.gog.com@other.example/on_login_success?code=secret",
            "https://embed.gog.com/on_login_success?code=one&code=two",
        ):
            with pytest.raises(LutrisError, match="full sign-in redirect URL"):
                await store_login.finish(request.id, reply)
        assert not responses
        await store_login.finish(
            request.id, "https://embed.gog.com/on_login_success?origin=client&code=fixture", str(cookie_file)
        )
        with pytest.raises(LutrisError, match="no longer available"):
            await store_login.finish(request.id, "https://embed.gog.com/on_login_success?code=fixture")
        assert (await services.get_source_status("gog")).signed_in

    asyncio.run(run())
    assert responses == ["https://embed.gog.com/on_login_success?code=fixture"]
    assert token.stat().st_mode & 0o777 == 0o600


def test_amazon_keeps_the_pkce_verifier_for_the_browser_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = tmp_path / ".amazon.user"
    received: list[str] = []

    def register(self: AmazonService, code: str) -> dict[str, object]:
        assert self.verifier
        received.append(hashlib.sha256(self.verifier).hexdigest())
        assert code == "fixture"
        return {"tokens": {}}

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(AmazonService, "user_path", str(token))
    monkeypatch.setattr(AmazonService, "generate_code_verifier", lambda self: b"fixture-pkce-verifier")
    monkeypatch.setattr(AmazonService, "register_device", register)

    async def run() -> None:
        request = await store_login.begin("amazon")
        assert "openid.oa2.code_challenge" in parse_qs(urlsplit(request.url).query)
        await store_login.finish(request.id, "https://www.amazon.com/?openid.oa2.authorization_code=fixture")
        assert (await services.get_source_status("amazon")).signed_in

    asyncio.run(run())
    assert received == [hashlib.sha256(b"fixture-pkce-verifier").hexdigest()]


def test_cookie_import_only_persists_the_selected_stores_cookies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / ".humblebundle.auth"
    source = tmp_path / "cookies.txt"
    source.write_text(
        "# Netscape HTTP Cookie File\n"
        "#HttpOnly_.humblebundle.com\tTRUE\t/\tTRUE\t0\tsession\thumble-session\n"
        ".other.example\tTRUE\t/\tTRUE\t0\tsession\tunrelated-session\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(HumbleBundleService, "cookies_path", str(target))

    async def run() -> None:
        request = await store_login.begin("humblebundle")
        await store_login.finish(request.id, str(source))
        assert (await services.get_source_status("humblebundle")).signed_in

    asyncio.run(run())
    cookies = HumbleBundleService().load_cookies()
    assert cookies is not None
    assert [(cookie.domain, cookie.name) for cookie in cookies] == [(".humblebundle.com", "session")]
    assert "unrelated-session" not in target.read_text(encoding="utf-8")
    assert target.stat().st_mode & 0o777 == 0o600


def test_ubisoft_combines_storage_values_and_only_saves_verified_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = tmp_path / ".ubisoft.token"
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(UbisoftConnectService, "token_path", str(token))

    def verify(self: UbisoftConnectClient, method: str, url: str, **kwargs: object) -> dict[str, str]:
        assert method == "post" and url.endswith("/v2/profiles/sessions")
        assert kwargs["timeout"] == 15
        return {"userId": "account", "nameOnPlatform": "Player"}

    monkeypatch.setattr(UbisoftConnectClient, "_do_request", verify)

    async def run() -> None:
        request = await store_login.begin("ubisoft")
        login = {"ticket": "fixture-ticket", "sessionId": "fixture-session"}
        with pytest.raises(LutrisError, match="login data as JSON"):
            await store_login.finish(request.id, json.dumps(login))
        with pytest.raises(LutrisError, match="did not accept"):
            await store_login.finish(request.id, json.dumps(login | {"userId": "other"}))
        assert not token.exists()
        await store_login.finish(
            request.id, json.dumps([login, {"rememberMeTicket": "fixture-refresh"}, {"userId": "account"}])
        )
        assert (await services.get_source_status("ubisoft")).signed_in

    asyncio.run(run())
    saved = json.loads(token.read_text(encoding="utf-8"))
    assert saved["userId"] == "account" and saved["username"] == "Player"
    assert saved["rememberMeTicket"] == "fixture-refresh"
    assert token.stat().st_mode & 0o777 == 0o600
