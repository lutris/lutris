"""Original Steam artwork lookup, with mocked HTTP and isolated cache files."""

import io
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, features

from lutris.services import steamgriddb as sg

ICON_HASH = "25a5" + "a" * 36
HEADER = "https://shared.steamstatic.com/store_item_assets/steam/apps/620/header.jpg"


def steam_entry(app_id="620", **metadata):
    return {
        "id": app_id,
        "metadata": metadata
        or {
            "header_image_full": {"english": "header.jpg"},
            "library_capsule_full": {
                "image": {"english": "library_600x900.jpg"},
                "image2x": {"english": "library_600x900_2x.jpg"},
            },
            "icon": ICON_HASH,
        },
    }


class TestOriginalArtwork(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.directory.name)
        self.stack.enter_context(patch.object(sg.settings, "CACHE_DIR", str(self.root)))
        self.key = self.stack.enter_context(patch.object(sg.settings, "read_setting", return_value="secret"))
        self.sleep = self.stack.enter_context(patch.object(sg.time, "sleep"))
        self.search = [{"id": 7, "name": "Portal 2"}]
        self.details = {"id": 7, "external_platform_data": {"steam": [steam_entry()]}}
        self.calls = []
        self.image = self.make_image((460, 215))
        self.real_request = sg._Request
        self.request = self.stack.enter_context(patch.object(sg, "_Request", side_effect=self.respond))

    @staticmethod
    def make_image(size, image_format="PNG"):
        output = io.BytesIO()
        Image.new("RGB", size).save(output, format=image_format)
        return output.getvalue()

    def respond(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not url.startswith(sg.API_URL):
            return SimpleNamespace(get=lambda: SimpleNamespace(status_code=200, content=self.image))
        data = self.search if "/search/" in url else self.details
        return SimpleNamespace(get=lambda: SimpleNamespace(status_code=200, json={"success": True, "data": data}))

    def lookup(self, title="Portal 2"):
        # A fresh endpoint cache per test assertion avoids masking changed mock responses.
        api = Mock()
        api.get.side_effect = [self.search, self.details]
        return sg.lookup_artwork(title, api)

    def test_original_metadata_mapping_and_auth_isolation(self):
        result = sg.lookup_artwork(" Portal 2 ")
        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.urls,
            {
                "banner": HEADER,
                "cover": "https://shared.steamstatic.com/store_item_assets/steam/apps/620/library_600x900_2x.jpg",
                "icon": f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/620/{ICON_HASH}.jpg",
            },
        )
        self.assertIn("/search/autocomplete/Portal%202", self.calls[0][0])
        self.assertIn("/games/id/7?platformdata=steam", self.calls[1][0])
        for _, kwargs in self.calls:
            self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret"})
        sg.download_artwork(result.urls["banner"], "banner")
        self.assertEqual(self.calls[-1][1], {})
        self.assertFalse(any("/grids/" in url or "/icons/" in url or "/games/steam/" in url for url, _ in self.calls))

    def test_exact_case_and_outer_whitespace_only(self):
        self.assertEqual(self.lookup("  PORTAL 2 ").status, "success")
        for title in ("Portal  2", "Portal\t2", "Portal", "Portal 2 Deluxe", "", None):
            with self.subTest(title=title):
                self.assertEqual(self.lookup(title).status, "no_match")
        self.search.append({"id": 8, "name": " portal 2 "})
        self.assertEqual(self.lookup().status, "ambiguous")

    def test_no_key_never_requests(self):
        self.key.return_value = " "
        self.assertEqual(sg.lookup_artwork("Portal 2"), sg.ArtworkLookup("missing_key", {}))
        self.request.assert_not_called()

    def test_empty_malformed_and_missing_metadata_are_distinct(self):
        self.search = []
        self.assertEqual(self.lookup().status, "no_match")
        for search in (None, {}, [{"id": True, "name": "Portal 2"}], [None], [{"id": 7, "name": None}]):
            self.search = search
            self.assertEqual(self.lookup().status, "error")
        self.search = [{"id": 7, "name": "Portal 2"}]
        for details in (
            None,
            {"id": 8},
            {"id": 7, "external_platform_data": []},
            {"id": 7, "external_platform_data": {"steam": {}}},
        ):
            self.details = details
            self.assertEqual(self.lookup().status, "error")
        for details in (
            [],
            {"id": 7},
            {"id": 7, "external_platform_data": None},
            {"id": 7, "external_platform_data": {"steam": []}},
            {"id": 7, "external_platform_data": {"steam": [{"id": "620", "metadata": None}]}},
        ):
            self.details = details
            self.assertEqual(self.lookup().status, "no_assets")

    def test_language_fallback_and_hashed_paths(self):
        entry = steam_entry(
            header_image_full={"english": "../bad", "german": "hash/header german.jpg"},
            library_capsule_full={"image2x": None, "image": {"english": "hash/library.jpg"}},
            clienticon=ICON_HASH,
        )
        self.details["external_platform_data"]["steam"] = [entry]
        result = self.lookup()
        self.assertEqual(result.urls["banner"], HEADER.replace("header.jpg", "hash/header%20german.jpg"))
        self.assertTrue(result.urls["cover"].endswith("/hash/library.jpg"))
        self.assertNotIn("icon", result.urls)

    def test_multiple_steam_entries_do_not_guess_editions(self):
        steam = self.details["external_platform_data"]["steam"]
        steam.insert(0, {"id": "999", "metadata": {}})
        self.assertEqual(self.lookup().status, "success")
        steam.append(steam_entry("621"))
        self.assertEqual(self.lookup().status, "ambiguous")
        steam[-1] = steam_entry("620", header_image_full={"english": "header.jpg"})
        self.assertEqual(len(self.lookup().urls), 3)
        steam.reverse()
        self.assertEqual(len(self.lookup().urls), 3)

    def test_unsafe_metadata_paths_hash_and_appid(self):
        for value in (
            "../header.jpg",
            "/header.jpg",
            "https://evil/a",
            "hash/../header.jpg",
            "hash/%2e%2e/a",
            "hash\\a",
            "a?b",
            "a#b",
            "a\nb",
            "//evil/a",
        ):
            self.details["external_platform_data"]["steam"] = [
                steam_entry(header_image_full={"english": value}, icon="not-a-hash")
            ]
            self.assertEqual(self.lookup().status, "no_assets")
        for app_id in ("../620", "https://evil", "0", 620, True, None):
            self.details["external_platform_data"]["steam"] = [steam_entry(app_id)]
            self.assertEqual(self.lookup().status, "no_assets")

    def test_download_preserves_source_dimensions_and_formats(self):
        for kind, size, image_format in (
            ("banner", (460, 215), "JPEG"),
            ("cover", (600, 900), "JPEG"),
            ("icon", (32, 32), "PNG"),
            ("cover", (1200, 1800), "JPEG"),
        ):
            with self.subTest(kind=kind, size=size):
                self.image = self.make_image(size, "JPEG" if kind == "icon" else "PNG")
                data = sg.download_artwork(HEADER, kind)
                with Image.open(io.BytesIO(data)) as image:
                    self.assertEqual(image.size, size)
                    self.assertEqual(image.format, image_format)
        self.assertFalse(list(self.root.iterdir()))

    def test_download_trust_boundary(self):
        for url in (
            "https://cdn.steamgriddb.com/a",
            "http://shared.steamstatic.com/a",
            "https://shared.steamstatic.com.evil/a",
            "https://user@shared.steamstatic.com/a",
            "https://shared.steamstatic.com:444/a",
            "https://shared.steamstatic.com/../a",
            "https://shared.steamstatic.com/%2e%2e/a",
            "https://shared.steamstatic.com/a?token=x",
            "https://shared.steamstatic.com/a#b",
            "file:///tmp/image",
        ):
            self.assertIsNone(sg.download_artwork(url, "icon"))
        self.assertIsNone(sg.download_artwork(HEADER, "unknown"))
        for kind in ("banners", "covers", "icons"):
            self.assertIsNone(sg.download_artwork(HEADER, kind))
        self.request.assert_not_called()
        for data in (b"not an image", b"x" * (sg.MAX_BYTES + 1)):
            self.image = data
            self.assertIsNone(sg.download_artwork(HEADER, "banner"))
        self.image = self.make_image((100, 100))
        with patch.object(sg, "MAX_PIXELS", 10):
            self.assertIsNone(sg.download_artwork(HEADER, "banner"))
        animated = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(
            animated, format="PNG", save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")], duration=100
        )
        self.image = animated.getvalue()
        self.assertIsNone(sg.download_artwork(HEADER, "icon"))

    def test_pure_encoder_preserves_resolution_and_shares_download_validation(self):
        for kind, size, expected_format in (
            ("banner", (460, 215), "JPEG"),
            ("cover", (600, 900), "JPEG"),
            ("icon", (32, 32), "PNG"),
        ):
            content = self.make_image(size)
            with Image.open(io.BytesIO(sg.encode_artwork(content, kind))) as image:
                self.assertEqual(image.size, size)
                self.assertEqual(image.format, expected_format)
        self.request.assert_not_called()
        for content in (None, "not bytes", b"", b"not an image", b"x" * (sg.MAX_BYTES + 1)):
            self.assertIsNone(sg.encode_artwork(content, "banner"))
        self.assertIsNone(sg.encode_artwork(self.image, "banners"))
        with patch.object(sg, "MAX_PIXELS", 10):
            self.assertIsNone(sg.encode_artwork(self.image, "banner"))
        with patch.object(sg, "encode_artwork", return_value=b"validated") as encode:
            self.assertEqual(sg.download_artwork(HEADER, "banner"), b"validated")
            encode.assert_called_once_with(self.image, "banner")
            encode.reset_mock()
            self.assertIsNone(sg.download_artwork("https://lutris.net/image.jpg", "banner"))
            encode.assert_not_called()

    @unittest.skipUnless(features.check("webp"), "Pillow has no WebP support")
    def test_static_webp_encoder_preserves_dimensions_and_canonical_formats(self):
        content = self.make_image((600, 900), "WEBP")
        for kind, expected_format in (("banner", "JPEG"), ("cover", "JPEG"), ("icon", "PNG")):
            with self.subTest(kind=kind):
                encoded = sg.encode_artwork(content, kind)
                with Image.open(io.BytesIO(encoded)) as image:
                    self.assertEqual(image.size, (600, 900))
                    self.assertEqual(image.format, expected_format)
        self.request.assert_not_called()

    @unittest.skipUnless(features.check("webp"), "Pillow has no WebP support")
    def test_animated_webp_rejected_when_supported(self):
        output = io.BytesIO()
        Image.new("RGB", (32, 32), "red").save(
            output,
            format="WEBP",
            save_all=True,
            append_images=[Image.new("RGB", (32, 32), "blue")],
            duration=100,
            loop=0,
        )
        content = output.getvalue()
        with Image.open(io.BytesIO(content)) as image:
            if not getattr(image, "is_animated", False):
                self.skipTest("Pillow has no animated WebP encoder")
        self.assertIsNone(sg.encode_artwork(content, "icon"))

    def test_redirect_handler_and_stream_caps(self):
        with self.assertRaises(sg.http.HTTPError):
            sg._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil/")
        with patch.object(sg.http, "get_opener", return_value=Mock()) as opener:
            self.real_request(HEADER)
            self.assertIsInstance(opener.call_args.args[1], sg._NoRedirect)
        request = self.real_request.__new__(self.real_request)
        request.total_size = sg.MAX_BYTES + 1
        response = Mock()
        with self.assertRaises(ValueError):
            list(request._iter_chunks(response))
        response.close.assert_called_once()
        request.total_size = 0
        request.downloaded_size = sg.MAX_BYTES
        request.stop_request = None
        request.buffer_size = 1
        response.read.return_value = b"x"
        with self.assertRaises(ValueError):
            list(request._iter_chunks(response))

    def test_cache_ttl_no_match_and_pacing(self):
        sg.lookup_artwork("Portal 2")
        self.request.reset_mock()
        self.assertEqual(sg.lookup_artwork("Portal 2").status, "success")
        self.request.assert_not_called()
        with patch.object(sg.time, "time", return_value=10**12):
            sg.lookup_artwork("Portal 2")
        self.assertEqual(self.request.call_count, 2)
        self.search = []
        self.assertEqual(sg.lookup_artwork("Unknown").status, "no_match")
        self.request.reset_mock()
        self.assertEqual(sg.lookup_artwork("Unknown").status, "no_match")
        self.request.assert_not_called()
        api = sg._API("secret")
        with patch.object(sg.time, "monotonic", return_value=10):
            api.get("/games/id/100?platformdata=steam")
            api.get("/games/id/101?platformdata=steam")
        self.sleep.assert_called_with(1.0)
        for path in (self.root / "steamgriddb").glob("*.json"):
            self.assertNotIn("secret", path.read_text())
            self.assertIsInstance(json.loads(path.read_text()), (list, dict))

    def test_404_cached_and_other_failures_not_persisted(self):
        with patch.object(sg, "_Request", side_effect=sg.http.HTTPError("missing", code=404)) as request:
            self.assertEqual(sg.lookup_artwork("Absent").status, "no_match")
            self.assertEqual(sg.lookup_artwork("Absent").status, "no_match")
            request.assert_called_once()
        for envelope in ({}, {"success": False, "data": []}, {"success": True, "data": None}):
            with patch.object(
                sg,
                "_Request",
                return_value=SimpleNamespace(
                    get=lambda envelope=envelope: SimpleNamespace(status_code=200, json=envelope)
                ),
            ) as request:
                api = sg._API("secret")
                self.assertEqual(sg.lookup_artwork("Broken", api).status, "error")
                self.assertEqual(sg.lookup_artwork("Broken", api).status, "error")
                request.assert_called_once()
        with patch.object(sg, "_Request", side_effect=OSError("secret")):
            self.assertEqual(sg.lookup_artwork("Broken").status, "error")
            self.assertIsNone(sg.download_artwork(HEADER, "banner"))

    def test_auth_and_rate_limits_propagate_sanitized_batch_stop(self):
        for error in (sg.http.UnauthorizedAccessError("secret"), sg.http.HTTPError("secret", code=429)):
            with patch.object(sg, "_Request", side_effect=error):
                for call in (lambda: sg.lookup_artwork("Portal 2"), lambda: sg.download_artwork(HEADER, "icon")):
                    with self.assertRaises(sg._StopBatch) as caught:
                        call()
                    self.assertNotIn("secret", str(caught.exception))
