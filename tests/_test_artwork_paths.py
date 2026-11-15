"""Managed artwork consumers respect the manager's ordered path contract."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lutris.gui.views.store_item import StoreItem
from lutris.services.service_media import MediaPath
from lutris.util import resources


class TestArtworkPaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = SimpleNamespace(size=(184, 69), api_field="banner")
        self.manager = SimpleNamespace(get_game_media_paths=Mock())
        self.modules = patch.dict(sys.modules, {"lutris.artwork": self.manager})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def path(self, relative, exists=False):
        path = os.path.join(self.temp.name, relative)
        if exists:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as image:
                image.write(b"image")
        return MediaPath(path, self.media)

    def test_slug_only_helper_preserves_legacy_path(self):
        with patch.object(resources.settings, "ICON_PATH", self.temp.name):
            self.assertEqual(resources.get_icon_path("same"), os.path.join(self.temp.name, "lutris_same.png"))
        self.manager.get_game_media_paths.assert_not_called()

    def test_duplicate_slugs_resolve_independent_private_artwork(self):
        paths = {game_id: self.path(f"{game_id}/auto/icon.png", True) for game_id in (1, 2)}
        self.manager.get_game_media_paths.side_effect = lambda row, media: [paths[row["id"]]]
        for game_id in (1, 2):
            self.assertEqual(
                resources.get_icon_path("same", game_data={"id": game_id, "slug": "same"}),
                paths[game_id].path,
            )

    def test_game_id_loads_database_row(self):
        row = {"id": 7, "slug": "same"}
        image = self.path("7/custom/icon.png", True)
        self.manager.get_game_media_paths.return_value = [image]
        with patch("lutris.database.games.get_game_by_field", return_value=row) as lookup:
            self.assertEqual(resources.get_icon_path("same", game_id=7), image.path)
        lookup.assert_called_once_with(7, "id")
        self.assertEqual(self.manager.get_game_media_paths.call_args.args[0], row)

    def test_legacy_is_read_only_fallback_for_missing_private_image(self):
        private = self.path("1/auto/banner.jpg")
        legacy = self.path("banners/same.jpg", True)
        self.manager.get_game_media_paths.return_value = [private, legacy]
        self.assertEqual(resources.get_banner_path("same", game_data={"id": 1}), legacy.path)
        self.assertFalse(os.path.exists(private.path))

    def test_missing_manual_image_does_not_resolve_auto(self):
        custom = self.path("1/custom/cover.jpg")
        self.path("1/auto/cover.jpg", True)
        self.manager.get_game_media_paths.return_value = [custom]
        self.assertEqual(resources.get_cover_path("same", game_data={"id": 1}), custom.path)

    def test_managed_store_item_does_not_try_service_fallback(self):
        media = Mock()
        media.api_field = "banner"
        row = {"id": 1, "slug": "same", "service_id": None}
        paths = [self.path("1/auto/banner.jpg")]
        self.manager.get_game_media_paths.return_value = paths
        self.assertEqual(StoreItem(row, None, media).get_media_paths(), paths)
        media.get_fallback_media_path.assert_not_called()
        self.manager.get_game_media_paths.assert_called_once_with(row, media, kind="banner")

    def test_service_item_uses_corresponding_managed_row(self):
        row = {"id": 2, "slug": "same"}
        item = StoreItem({"appid": "123", "service": "steam", "slug": "same"}, None, self.media)
        item.apply_installed_game_data(row)
        self.manager.get_game_media_paths.return_value = [self.path("2/custom/banner.jpg", True)]
        self.assertEqual(item.get_media_paths(), self.manager.get_game_media_paths.return_value)
        self.manager.get_game_media_paths.assert_called_once_with(row, self.media, kind="banner")


class TestSteamArtworkPaths(unittest.TestCase):
    def test_mapped_steam_media_uses_private_role_and_preserves_size(self):
        from lutris import settings
        from lutris.services.steam import SteamBanner, SteamCover, SteamService

        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "DATA_DIR", directory):
            for media_type, kind, filename in (
                (SteamBanner, "banner", "banner.jpg"),
                (SteamCover, "cover", "cover.jpg"),
            ):
                with self.subTest(kind=kind), patch.object(media_type, "dest_path", directory):
                    media = media_type()
                    item = StoreItem({"appid": "123", "service": "steam", "slug": "same"}, SteamService, media)
                    item.apply_installed_game_data({"id": 42, "slug": "same"})
                    paths = item.get_media_paths()
                    self.assertEqual(paths[0].path, os.path.join(directory, "artwork", "42", "auto", filename))
                    self.assertIs(paths[0].service_media, media)
                    self.assertEqual(paths[0].size, media.size)

    def test_unsupported_role_keeps_legacy_behavior(self):
        from lutris.services.service_media import ServiceMedia

        class UnsupportedMedia(ServiceMedia):
            api_field = "appid"
            service = "example"
            size = (184, 69)

        with tempfile.TemporaryDirectory() as directory:
            UnsupportedMedia.dest_path = directory
            UnsupportedMedia.file_patterns = ["%s.jpg"]
            media = UnsupportedMedia()
            service = SimpleNamespace(medias={"unknown": UnsupportedMedia}, extra_medias={})
            item = StoreItem({"id": 42, "slug": "same", "service_id": None}, service, media)
            legacy = media.get_possible_media_paths("same")
            with patch.object(media, "get_fallback_media_path", return_value=None):
                self.assertEqual([path.path for path in item.get_media_paths()], [path.path for path in legacy])
