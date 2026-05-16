import importlib.util
import os
import sys
import types


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOG_PATH = os.path.join(REPO_ROOT, "lutris", "services", "gog.py")


TEST_IDS = ["2057001589", "1575323267", "1344230395"]


def _make_module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


def _install_stubs():
    if "lutris.services.gog" in sys.modules:
        return sys.modules["lutris.services.gog"]

    lutris_pkg = _make_module("lutris")
    lutris_pkg.__path__ = []

    settings_mod = _make_module(
        "lutris.settings",
        CACHE_DIR="/tmp/lutris-test-cache",
    )

    exceptions_mod = _make_module(
        "lutris.exceptions",
        AuthenticationError=type("AuthenticationError", (Exception,), {}),
        UnavailableGameError=type("UnavailableGameError", (Exception,), {}),
    )

    installer_mod = _make_module(
        "lutris.installer",
        AUTO_ELF_EXE="AUTO_ELF_EXE",
        AUTO_WIN32_EXE="AUTO_WIN32_EXE",
    )
    installer_mod.__path__ = []

    installer_file_mod = _make_module(
        "lutris.installer.installer_file",
        InstallerFile=type("InstallerFile", (object,), {}),
    )
    installer_file_collection_mod = _make_module(
        "lutris.installer.installer_file_collection",
        InstallerFileCollection=type("InstallerFileCollection", (object,), {}),
    )

    runners_mod = _make_module("lutris.runners", get_runner_human_name=lambda runner: runner)

    service_base_mod = _make_module(
        "lutris.services.base",
        SERVICE_LOGIN=object(),
        AuthTokenExpiredError=type("AuthTokenExpiredError", (Exception,), {}),
        OnlineService=type(
            "OnlineService",
            (object,),
            {
                "__init__": lambda self: None,
                "get_installed_slug": lambda self, db_game: db_game.get("slug", "installed-game"),
                "is_authenticated": lambda self: True,
            },
        ),
    )

    service_game_mod = _make_module("lutris.services.service_game", ServiceGame=type("ServiceGame", (object,), {}))
    service_media_mod = _make_module("lutris.services.service_media", ServiceMedia=type("ServiceMedia", (object,), {}))

    util_pkg = _make_module("lutris.util")
    util_pkg.__path__ = []
    i18n_mod = _make_module("lutris.util.i18n", get_lang=lambda: "en")
    system_mod = _make_module("lutris.util.system", path_exists=lambda path: False)
    gog_downloader_mod = _make_module("lutris.util.gog_downloader", GOGDownloader=type("GOGDownloader", (object,), {}))
    http_mod = _make_module(
        "lutris.util.http",
        HTTPError=type("HTTPError", (Exception,), {}),
        UnauthorizedAccessError=type("UnauthorizedAccessError", (Exception,), {}),
        Request=type("Request", (object,), {}),
    )
    log_mod = _make_module(
        "lutris.util.log",
        logger=types.SimpleNamespace(
            debug=lambda *args, **kwargs: None,
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        ),
    )
    strings_mod = _make_module(
        "lutris.util.strings",
        human_size=lambda size: str(size),
        slugify=lambda value: value.lower().replace(" ", "-"),
    )

    util_pkg.i18n = i18n_mod
    util_pkg.system = system_mod

    services_pkg = _make_module("lutris.services")
    services_pkg.__path__ = []
    services_pkg.base = service_base_mod
    services_pkg.service_game = service_game_mod
    services_pkg.service_media = service_media_mod

    lutris_pkg.settings = settings_mod
    lutris_pkg.exceptions = exceptions_mod
    lutris_pkg.installer = installer_mod
    lutris_pkg.runners = runners_mod
    lutris_pkg.services = services_pkg
    lutris_pkg.util = util_pkg

    sys.modules.update(
        {
            "lutris": lutris_pkg,
            "lutris.settings": settings_mod,
            "lutris.exceptions": exceptions_mod,
            "lutris.installer": installer_mod,
            "lutris.installer.installer_file": installer_file_mod,
            "lutris.installer.installer_file_collection": installer_file_collection_mod,
            "lutris.runners": runners_mod,
            "lutris.services": services_pkg,
            "lutris.services.base": service_base_mod,
            "lutris.services.service_game": service_game_mod,
            "lutris.services.service_media": service_media_mod,
            "lutris.util": util_pkg,
            "lutris.util.i18n": i18n_mod,
            "lutris.util.system": system_mod,
            "lutris.util.gog_downloader": gog_downloader_mod,
            "lutris.util.http": http_mod,
            "lutris.util.log": log_mod,
            "lutris.util.strings": strings_mod,
        }
    )

    spec = importlib.util.spec_from_file_location("lutris.services.gog", GOG_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lutris.services.gog"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GOG = _install_stubs()
GOGService = GOG.GOGService


class ProductSequence:
    """Minimal stand-in for the `products` payload used by get_game_dlcs()."""

    def __init__(self, ids):
        self._ids = list(ids)

    def __iter__(self):
        for product_id in self._ids:
            yield {"id": product_id}

    def size(self):
        return len(self._ids)


def _game_details_with_products(expanded_url, ids_list):
    return {"dlcs": {"expanded_all_products_url": expanded_url, "products": ProductSequence(ids_list)}}


def _fake_downloads_item(product_id, slug=None, title=None):
    slug = slug or f"slug-{product_id}"
    title = title or f"Title {product_id}"
    return {
        "id": int(product_id),
        "slug": slug,
        "title": title,
        "is_installable": True,
        "downloads": {
            "installers": [
                {
                    "id": f"installer-{product_id}",
                    "os": "windows",
                    "language": "en",
                    "language_full": "English",
                    "name": title,
                    "version": "1.0",
                    "files": [],
                }
            ],
            "bonus_content": [
                {
                    "id": f"bonus-{product_id}",
                    "name": "manual",
                    "type": "manual",
                    "total_size": 123,
                    "files": [{"downlink": f"https://example.invalid/{product_id}/bonus.zip"}],
                }
            ],
            "patches": [],
        },
    }


def test_get_game_dlcs_splitting_and_merging(monkeypatch):
    """Exercise the single-request and multi-request paths while keeping the test isolated."""
    service = GOGService()
    requested_urls = []

    def fake_make_api_request(self, url):
        requested_urls.append(url)
        start = url.find("ids=")
        if start == -1:
            return []
        start += 4
        end = url.find("&", start)
        if end == -1:
            end = len(url)
        ids_requested = [item for item in url[start:end].split(",") if item]
        return [{"product_id": product_id, "downloads": {"installers": [], "bonus_content": [], "patches": []}} for product_id in ids_requested]

    monkeypatch.setattr(GOGService, "make_api_request", fake_make_api_request)

    cases = {
        "2057001589": [str(i) for i in range(1, 121)],
        "1575323267": ["42"],
        "1344230395": [str(i) for i in range(1001, 1015)],
    }

    for product_id, ids in cases.items():
        requested_urls.clear()
        expanded_url = "https://api.gog.com/products?ids=" + ",".join(ids) + "&expand=downloads"
        game_details = _game_details_with_products(expanded_url, ids)
        monkeypatch.setattr(GOGService, "get_game_details", lambda self, pid, _details=game_details: _details)

        result = service.get_game_dlcs(product_id)

        assert isinstance(result, list)
        assert result, f"Expected DLC data for {product_id}"
        assert all(set(item.keys()) == set(result[0].keys()) for item in result)

        if len(ids) > 50:
            assert len(requested_urls) > 1
        else:
            assert len(requested_urls) == 1


def test_get_dlc_installers(monkeypatch):
    """Standalone integration test for DLC installer generation."""
    service = GOGService()
    service.get_installed_slug = lambda db_game: "example-game"
    service.get_game_dlcs = lambda gogid: [
        _fake_downloads_item("100", slug="dlc-one", title="DLC One"),
        _fake_downloads_item("200", slug="dlc-two", title="DLC Two"),
    ]

    db_game = {
        "service_id": "1344230395",
        "name": "Fake Game",
        "runner": "wine",
        "slug": "fake-game",
        "installer_slug": "fake-installer",
    }

    installers = service.get_dlc_installers(db_game)

    assert len(installers) == 2
    assert all(set(installer.keys()) == set(installers[0].keys()) for installer in installers)
    assert {installer["runner"] for installer in installers} == {"wine"}
    assert {installer["dlcid"] for installer in installers} == {"100", "200"}


def test_get_extras(monkeypatch):
    """Standalone integration test for bonus content aggregation across a game and its DLCs."""
    service = GOGService()

    game = {
        "id": 1344230395,
        "title": "DOOM Eternal",
        "is_installable": True,
        "downloads": {
            "bonus_content": [
                {
                    "id": "game-bonus-1",
                    "name": "manual",
                    "type": "pdf",
                    "total_size": 100,
                    "files": [{"downlink": "https://example.invalid/game/manual.zip"}],
                }
            ]
        },
    }
    dlcs = [
        {
            "id": 1085707627,
            "title": "DLC One",
            "is_installable": True,
            "downloads": {
                "bonus_content": [
                    {
                        "id": "dlc-bonus-1",
                        "name": "soundtrack",
                        "type": "mp3",
                        "total_size": 200,
                        "files": [{"downlink": "https://example.invalid/dlc/soundtrack.zip"}],
                    }
                ]
            },
        }
    ]

    monkeypatch.setattr(GOGService, "get_game_details", lambda self, gogid: game)
    monkeypatch.setattr(GOGService, "get_game_dlcs", lambda self, gogid: dlcs)

    extras = service.get_extras("1344230395")

    assert set(extras.keys()) == {"DOOM Eternal", "DLC One"}
    assert all(isinstance(value, list) and value for value in extras.values())
    all_item_keys = [set(item.keys()) for value in extras.values() for item in value]
    assert all(key_set == all_item_keys[0] for key_set in all_item_keys)