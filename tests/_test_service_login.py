"""Logging in to services, and runner actions, ask the user through delegates."""

from unittest.mock import MagicMock, patch

import pytest

from lutris.delegates import Delegate, InstallUIDelegate, ServiceLoginUIDelegate
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.itchio import ItchIoService


class RecordingLoginDelegate(ServiceLoginUIDelegate):
    """Answers with canned replies and records what it was asked."""

    def __init__(self, answer=False, text=None, cookies=None, file=None):
        self.answer = answer
        self.text = text
        self.cookies = cookies
        self.file = file
        self.calls = []

    def ask_question(self, title, question_markup):
        self.calls.append("ask_question")
        return self.answer

    def ask_for_text(self, title, question_markup, initial_value=""):
        self.calls.append("ask_for_text")
        return self.text

    def ask_for_file(self, message, default_path=None):
        self.calls.append("ask_for_file")
        return self.file

    def ask_for_humble_bundle_cookies(self):
        self.calls.append("ask_for_humble_bundle_cookies")
        return self.cookies

    def show_web_login(self, service):
        self.calls.append("show_web_login")

    def install_service_launcher(self, service):
        self.calls.append("install_service_launcher")


@pytest.fixture
def logins(fake_main_loop):
    """The services SERVICE_LOGIN fired for."""
    logged_in = []
    registration = SERVICE_LOGIN.register(logged_in.append)
    yield logged_in
    registration.unregister()


def test_itch_io_saves_the_api_key_the_user_gives(tmp_path, monkeypatch, fake_main_loop, logins):
    service = ItchIoService()
    monkeypatch.setattr(service, "api_key_path", str(tmp_path / "api-key"))

    service.login(RecordingLoginDelegate(text="secret-key"))
    fake_main_loop.run_pending()

    assert (tmp_path / "api-key").read_text() == "secret-key"
    assert logins == [service]


def test_itch_io_logs_out_when_the_user_cancels(tmp_path, monkeypatch, fake_main_loop, logins):
    service = ItchIoService()
    monkeypatch.setattr(service, "api_key_path", str(tmp_path / "api-key"))
    logout = MagicMock()
    monkeypatch.setattr(service, "logout", logout)

    service.login(RecordingLoginDelegate(text=None))
    fake_main_loop.run_pending()

    logout.assert_called_once()
    assert logins == []


def test_humble_bundle_uses_the_cookies_the_user_provides(tmp_path, monkeypatch, fake_main_loop, logins):
    service = HumbleBundleService()
    monkeypatch.setattr(service, "cookies_path", str(tmp_path / "cookies"))
    delegate = RecordingLoginDelegate(answer=True, cookies="cookie data")

    service.login(delegate)
    fake_main_loop.run_pending()

    assert delegate.calls == ["ask_question", "ask_for_humble_bundle_cookies"]
    assert (tmp_path / "cookies").read_text() == "cookie data"
    assert logins == [service]


def test_humble_bundle_falls_back_to_the_web_login(tmp_path, monkeypatch, fake_main_loop):
    service = HumbleBundleService()
    monkeypatch.setattr(service, "cookies_path", str(tmp_path / "cookies"))
    delegate = RecordingLoginDelegate(answer=False)

    service.login(delegate)

    assert delegate.calls == ["ask_question", "show_web_login"]


def test_service_with_a_launcher_installs_it_before_logging_in(monkeypatch):
    service = OnlineService()
    monkeypatch.setattr(service, "client_installer", "some-launcher")
    monkeypatch.setattr(service, "is_launcher_installed", lambda: False)
    delegate = RecordingLoginDelegate()

    service.login(delegate)

    assert delegate.calls == ["install_service_launcher"]


def test_default_delegates_never_wait_for_a_user():
    delegate = ServiceLoginUIDelegate()
    assert delegate.ask_question("Title", "Really?") is False
    assert delegate.ask_for_text("Title", "Name?") is None
    assert delegate.ask_for_file("Pick one") is None
    assert delegate.ask_for_humble_bundle_cookies() is None
    delegate.show_notice("Hello")
    delegate.show_web_login(MagicMock())
    # The installer's own yes/no question still defaults to yes
    assert InstallUIDelegate().show_install_yesno_inquiry("Install?", "Title") is True


def test_wine_runs_the_executable_the_user_picks():
    from lutris.runners.wine import wine

    runner = wine()
    delegate = RecordingLoginDelegate(file="/games/setup.exe")
    with patch.object(runner, "prelaunch"), patch.object(runner, "_run_executable") as run_executable:
        runner.run_wineexec(delegate)

    run_executable.assert_called_once_with("/games/setup.exe")


def test_wine_runs_nothing_when_the_user_cancels():
    from lutris.runners.wine import wine

    runner = wine()
    with patch.object(runner, "_run_executable") as run_executable:
        runner.run_wineexec(Delegate())

    run_executable.assert_not_called()
