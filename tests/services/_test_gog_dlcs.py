"""
Comprehensive test class for GOGService.get_game_dlcs() function.

Tests the ability to:
1. Accept a numerical product ID
2. Parse it into API requests
3. Handle DLC lists with more than 50 items
4. Fetch DLC data in multiple requests when needed
5. Merge results into unified JSON
"""

import importlib.util
import os
import sys
import types
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOG_PATH = os.path.join(REPO_ROOT, "lutris", "services", "gog.py")


def _make_module(name, **attrs):
    """Create a mock module for testing."""
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


def _install_stubs():
    """Install all required module stubs for testing."""
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


class TestGOGDLCFetcher(unittest.TestCase):
    """Test suite for GOGService.get_game_dlcs() function."""

    def setUp(self):
        """Setup test fixtures before each test."""
        self.service = GOGService()
        self.requested_urls = []
        self.make_api_request_calls = []

    def _create_dlc_product(self, product_id, title=None, slug=None):
        """Helper to create a mock DLC product object."""
        return {
            "id": int(product_id),
            "title": title or f"DLC {product_id}",
            "slug": slug or f"dlc-{product_id}",
            "purchase_link": f"https://www.gog.com/en/checkout/manual/dlc-{product_id}",
            "content_system_compatibility": {"windows": True, "osx": True, "linux": True},
            "languages": {"de": "Deutsch", "en": "English", "es": "español", "fr": "français"},
            "links": {
                "purchase_link": f"https://www.gog.com/en/checkout/manual/dlc-{product_id}",
                "product_card": f"https://www.gog.com/game/dlc-{product_id}",
                "support": f"https://www.gog.com/support/dlc-{product_id}",
                "forum": "https://www.gog.com/forum/series",
            },
            "in_development": {"active": False, "until": None},
            "is_secret": False,
            "is_installable": True,
            "game_type": "dlc",
            "is_pre_order": False,
            "release_date": "2022-11-23T15:45:00+0200",
            "images": {
                "background": f"//images.gog-statics.com/{product_id}_bg.jpg",
                "logo": f"//images.gog-statics.com/{product_id}_logo.jpg",
                "icon": f"//images.gog-statics.com/{product_id}_icon.png",
            },
            "dlcs": [],
            "downloads": {
                "installers": [
                    {
                        "id": f"installer_{product_id}",
                        "name": title or f"DLC {product_id}",
                        "os": "windows",
                        "language": "en",
                        "language_full": "English",
                        "version": "1.0",
                        "total_size": 1024 * 1024 * (int(product_id) % 100),
                        "files": [
                            {"id": f"file_{product_id}", "size": 1024, "downlink": f"https://example.com/{product_id}"}
                        ],
                    }
                ],
                "patches": [],
                "language_packs": [],
                "bonus_content": [],
            },
        }

    def _create_game_details_response(self, product_id, dlc_ids):
        """Helper to create a game details response with DLC list."""
        dlc_products = [
            {
                "id": int(pid),
                "link": f"https://api.gog.com/products/{pid}",
                "expanded_link": f"https://api.gog.com/products/{pid}?expand=downloads",
            }
            for pid in dlc_ids
        ]

        base_ids = ",".join(str(pid) for pid in dlc_ids)
        all_products_url = f"https://api.gog.com/products?ids={base_ids}&expand=downloads"
        expanded_all_products_url = f"https://api.gog.com/products?ids={base_ids}&expand=downloads"

        return {
            "id": int(product_id),
            "title": f"Game {product_id}",
            "slug": f"game-{product_id}",
            "dlcs": {
                "products": dlc_products,
                "all_products_url": all_products_url,
                "expanded_all_products_url": expanded_all_products_url,
            },
            "downloads": {"installers": [], "patches": [], "language_packs": [], "bonus_content": []},
        }

    def _mock_make_api_request(self, url):
        """Mock implementation of make_api_request for testing."""
        self.requested_urls.append(url)
        self.make_api_request_calls.append(url)

        # Handle product detail requests
        if "ids=" in url:
            # Extract IDs from URL
            start = url.find("ids=")
            if start != -1:
                start += 4
                end = url.find("&", start)
                if end == -1:
                    end = len(url)
                ids_string = url[start:end]
                ids_list = [pid.strip() for pid in ids_string.split(",") if pid.strip()]

                # Return mock product details for each ID
                return [self._create_dlc_product(pid) for pid in ids_list]

        return []

    def test_single_request_path_with_few_dlcs(self):
        """Test get_game_dlcs with fewer than 50 DLCs (single request)."""
        product_id = "1575323267"
        dlc_ids = list(range(1, 25))  # 24 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == len(dlc_ids), f"Expected {len(dlc_ids)} DLCs, got {len(result)}"
        assert len(self.make_api_request_calls) == 1, "Should make exactly 1 API request for <50 DLCs"
        assert all("expanded_all_products_url" in game_details["dlcs"] for _ in [None])

    def test_multi_request_path_with_many_dlcs(self):
        """Test get_game_dlcs with exactly 72 DLCs (like Europa Universalis IV)."""
        product_id = "2057001589"
        dlc_ids = list(range(1078355380, 1078355380 + 72))  # 72 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 72, f"Expected 72 DLCs, got {len(result)}"
        # 72 DLCs should be split into 2 requests: 50 + 22
        assert len(self.make_api_request_calls) == 2, (
            f"Expected 2 API requests for 72 DLCs, got {len(self.make_api_request_calls)}"
        )

        # Verify all DLCs are present in result
        result_ids = {item["id"] for item in result}
        expected_ids = set(dlc_ids)
        assert result_ids == expected_ids, "All DLC IDs should be present in the result"

    def test_multi_request_batching_exactly_100_dlcs(self):
        """Test batching with exactly 100 DLCs (2 full batches)."""
        product_id = "1344230395"
        dlc_ids = list(range(1001, 1101))  # 100 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert len(result) == 100, f"Expected 100 DLCs, got {len(result)}"
        assert len(self.make_api_request_calls) == 2, "Expected 2 API requests for 100 DLCs"

        # Verify batches are correctly sized
        for i, url in enumerate(self.make_api_request_calls):
            start = url.find("ids=") + 4
            end = url.find("&", start) if "&" in url[start:] else len(url)
            ids_in_batch = len(url[start:end].split(","))
            assert ids_in_batch <= 50, f"Batch {i} has {ids_in_batch} IDs, should be <= 50"

    def test_multi_request_batching_151_dlcs(self):
        """Test batching with 151 DLCs (4 batches: 50 + 50 + 50 + 1)."""
        product_id = "1111111151"
        dlc_ids = list(range(2000, 2151))  # 151 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert len(result) == 151, f"Expected 151 DLCs, got {len(result)}"
        assert len(self.make_api_request_calls) == 4, "Expected 4 API requests for 151 DLCs (50+50+50+1)"

    def test_empty_dlc_list(self):
        """Test get_game_dlcs when game has no DLCs."""
        product_id = "1000000001"

        # Setup mocks - game with no DLCs
        game_details = {
            "id": int(product_id),
            "title": "Game Without DLCs",
            "dlcs": {"products": [], "expanded_all_products_url": "", "all_products_url": ""},
        }
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 0, "Result should be empty for game with no DLCs"
        assert len(self.make_api_request_calls) == 0, "No API requests should be made for empty DLC list"

    def test_no_dlcs_key(self):
        """Test get_game_dlcs when game details have no 'dlcs' key."""
        product_id = "game_without_dlcs_key"

        # Setup mocks
        game_details = {
            "id": int(product_id) if product_id.isdigit() else 999,
            "title": "Game Without DLCs Key",
        }
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 0, "Result should be empty when 'dlcs' key is missing"

    def test_unified_json_structure(self):
        """Test that unified JSON has consistent structure across all DLCs."""
        product_id = "2057001589"
        dlc_ids = list(range(1, 73))  # 72 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify structure consistency
        assert len(result) > 0, "Result should not be empty"

        # Get keys from first item as reference
        first_item_keys = set(result[0].keys())

        # Verify all items have same keys
        for item in result:
            assert isinstance(item, dict), "Each item should be a dictionary"
            assert set(item.keys()) == first_item_keys, "All items should have same keys"

        # Verify required keys exist
        required_keys = {"id", "title", "slug", "downloads", "dlcs"}
        assert required_keys.issubset(first_item_keys), (
            f"Missing required keys. Expected {required_keys}, got {first_item_keys}"
        )

    def test_product_ids_correctly_extracted(self):
        """Test that product IDs are correctly extracted from game details."""
        product_id = "1111111100"
        dlc_ids = [str(i) for i in range(100, 110)]  # 10 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify IDs match
        result_ids = sorted([item["id"] for item in result])
        expected_ids = sorted([int(pid) for pid in dlc_ids])
        assert result_ids == expected_ids, f"IDs don't match. Expected {expected_ids}, got {result_ids}"

    def test_batching_with_exact_50_boundary(self):
        """Test batching behavior with exactly 50 DLCs."""
        product_id = "1111111050"
        dlc_ids = list(range(1, 51))  # Exactly 50 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify - with exactly 50, should still use multi-request path if > 50
        # But since it's exactly 50, let's check if it uses the expanded_all_products_url
        assert len(result) == 50, f"Expected 50 DLCs, got {len(result)}"

    def test_returns_list_of_dicts(self):
        """Test that the function always returns a list of dictionaries."""
        product_id = "1111111075"
        dlc_ids = list(range(1, 76))  # 75 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify
        assert isinstance(result, list), "Return type must be a list"
        assert all(isinstance(item, dict) for item in result), "All items in list must be dictionaries"

    def test_api_url_construction(self):
        """Test that API URLs are correctly constructed."""
        product_id = "1111111060"
        dlc_ids = list(range(500, 560))  # 60 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute
        result = self.service.get_game_dlcs(product_id)

        # Verify API URLs
        assert len(self.make_api_request_calls) > 0, "At least one API request should be made"
        for url in self.make_api_request_calls:
            assert "api.gog.com" in url, f"URL should contain api.gog.com: {url}"
            assert "ids=" in url, f"URL should contain ids parameter: {url}"
            assert "expand=downloads" in url, f"URL should request downloads expansion: {url}"

    def test_deterministic_output_order(self):
        """Test that output maintains consistent ordering."""
        product_id = "1111111200"
        dlc_ids = list(range(1, 101))  # 100 DLCs

        # Setup mocks
        game_details = self._create_game_details_response(product_id, dlc_ids)
        self.service.get_game_details = lambda pid: game_details
        self.service.make_api_request = self._mock_make_api_request

        # Execute twice
        result1 = self.service.get_game_dlcs(product_id)
        self.requested_urls.clear()
        self.make_api_request_calls.clear()
        result2 = self.service.get_game_dlcs(product_id)

        # Verify order is the same
        ids1 = [item["id"] for item in result1]
        ids2 = [item["id"] for item in result2]
        assert ids1 == ids2, "Output order should be deterministic"


if __name__ == "__main__":
    unittest.main()
