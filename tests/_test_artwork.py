import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import PropertyMock, patch

from PIL import Image

from lutris import artwork, settings
from lutris.database import games, schema
from lutris.game import Game
from lutris.services.base import LutrisBanner, LutrisCoverart
from lutris.services.steamgriddb import ArtworkLookup


class TestArtwork(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.values = {"artwork_source": "lutris", "steamgriddb_api_key": "test-key"}
        for name, value in {
            "DB_PATH": str(self.root / "games.db"),
            "DATA_DIR": str(self.root),
            "CACHE_DIR": str(self.root / "cache"),
        }.items():
            self.start_patch(patch.object(settings, name, value))
        self.start_patch(
            patch.object(settings, "read_setting", side_effect=lambda name, *args, **kwargs: self.values.get(name))
        )
        self.start_patch(patch.object(artwork.MEDIA_CACHE_INVALIDATED, "fire"))
        schema.syncdb()
        self.api_games = self.start_patch(
            patch(
                "lutris.api.get_api_games",
                return_value=[
                    {
                        "slug": "same",
                        "aliases": [],
                        "banner": "https://lutris.net/banner.jpg",
                        "icon": "https://lutris.net/icon.png",
                        "coverart": "https://images.igdb.com/cover.jpg",
                    }
                ],
            )
        )
        self.lookup = self.start_patch(
            patch.object(
                artwork.steamgriddb,
                "lookup_artwork",
                return_value=ArtworkLookup("success", {"banner": "banner", "cover": "cover", "icon": "icon"}),
            )
        )
        self.image = self.image_bytes()
        self.original_lutris_download = artwork._download_lutris
        self.lutris_download = self.start_patch(patch.object(artwork, "_download_lutris", return_value=self.image))
        self.steam_download = self.start_patch(
            patch.object(artwork.steamgriddb, "download_artwork", return_value=self.image)
        )

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def test_queued_stale_row_skips_provider_lookup_and_downloads(self):
        for source in ("lutris", "steamgriddb"):
            with self.subTest(source=source):
                self.values["artwork_source"] = source
                game_id = self.add()
                snapshot = dict(self.row(game_id), _source=source)
                self.values["artwork_source"] = "steamgriddb" if source == "lutris" else "lutris"
                result = artwork._refresh_one(snapshot, ["banner"], object(), {"same": {"banner": "banner"}})
                self.assertEqual(result.status, "stale")
        self.lookup.assert_not_called()
        self.lutris_download.assert_not_called()
        self.steam_download.assert_not_called()

    def test_source_change_after_first_publication_stops_remaining_downloads(self):
        for source in ("lutris", "steamgriddb"):
            with self.subTest(source=source):
                self.values["artwork_source"] = source
                game_id = self.add()
                snapshot = dict(self.row(game_id), _source=source)
                publish = artwork._publish

                def publish_then_switch(*args, publish=publish, source=source, **kwargs):
                    result = publish(*args, **kwargs)
                    self.values["artwork_source"] = "steamgriddb" if source == "lutris" else "lutris"
                    return result

                self.lutris_download.reset_mock()
                self.steam_download.reset_mock()
                with patch.object(artwork, "_publish", side_effect=publish_then_switch):
                    result = artwork._refresh_one(
                        snapshot,
                        ["banner", "cover", "icon"],
                        object(),
                        {"same": {"banner": "banner", "cover": "cover", "icon": "icon"}},
                    )
                self.assertEqual(result.updated_kinds, ("banner",))
                self.assertTrue(artwork._path(game_id, "banner").exists())
                download = self.steam_download if source == "steamgriddb" else self.lutris_download
                download.assert_called_once_with("banner", "banner")

    def test_new_custom_flag_skips_only_that_slot_before_download(self):
        game_id = self.add()
        snapshot = dict(self.row(game_id), _source="lutris")
        games.update_existing(id=game_id, has_custom_banner=1)
        result = artwork._refresh_one(
            snapshot, ["banner", "icon"], None, {"same": {"banner": "banner", "icon": "icon"}}
        )
        self.assertEqual(result.updated_kinds, ("icon",))
        self.lutris_download.assert_called_once_with("icon", "icon")

    @staticmethod
    def image_bytes(color="red"):
        output = io.BytesIO()
        Image.new("RGB", (8, 8), color).save(output, "PNG")
        return output.getvalue()

    def add(self, **kwargs):
        return games.add_game(name="Game", slug="same", **kwargs)

    def row(self, game_id):
        return games.get_game_by_field(game_id, "id")

    def test_source_choice_and_explicit_null_persistence_on_game_reload(self):
        for source in (None, "lutris", "steamgriddb"):
            game_id = self.add(artwork_source=source)
            game = Game(game_id)
            self.assertEqual(game.artwork_source, source)
            with (
                patch.object(Game, "config", new_callable=PropertyMock, return_value=None),
                patch.object(Game, "set_platform_from_runner"),
            ):
                game.save(no_signal=True)
            self.assertEqual(Game(game_id).artwork_source, source)
            self.values["artwork_source"] = "steamgriddb"
            self.assertEqual(artwork.get_effective_source(self.row(game_id)), source or "steamgriddb")

    def test_duplicate_slugs_are_isolated_and_custom_slot_never_fetched(self):
        first = self.add(has_custom_banner=1)
        second = self.add()
        results = artwork.refresh_artwork()
        self.assertEqual(results[first].updated_kinds, ("cover", "icon"))
        self.assertEqual(results[second].updated_kinds, ("banner", "cover", "icon"))
        self.assertFalse(artwork._path(first, "banner").exists())
        self.assertTrue(artwork._path(second, "banner").exists())
        self.assertNotEqual(artwork._path(first, "cover"), artwork._path(second, "cover"))
        self.api_games.assert_called_once_with(["same"])

    def test_global_force_excludes_all_explicit_overrides(self):
        inherited = self.add()
        same_as_global = self.add(artwork_source="lutris")
        other = self.add(artwork_source="steamgriddb")
        results = artwork.refresh_artwork(force=True, inherited_only=True)
        self.assertEqual(set(results), {inherited})
        self.assertFalse(artwork._directory(same_as_global).exists())
        self.assertFalse(artwork._directory(other).exists())
        self.lookup.assert_not_called()

    def test_per_game_force_refreshes_only_its_unprotected_slots(self):
        selected = self.add(artwork_source="steamgriddb", has_custom_icon=1)
        other = self.add()
        result = artwork.refresh_artwork(iter([selected]), force=True)
        self.assertEqual(set(result), {selected})
        self.assertEqual(result[selected].updated_kinds, ("banner", "cover"))
        self.assertFalse(artwork._directory(other).exists())
        self.api_games.assert_not_called()

    def test_selected_provider_only_and_no_key_never_calls_other_provider(self):
        game_id = self.add(artwork_source="steamgriddb")
        self.lookup.return_value = ArtworkLookup("no_match", {})
        self.assertEqual(artwork.refresh_artwork()[game_id].status, "no_match")
        self.api_games.assert_not_called()
        self.lutris_download.assert_not_called()
        self.values["steamgriddb_api_key"] = ""
        self.lookup.reset_mock()
        self.assertEqual(artwork.refresh_artwork()[game_id].status, "missing_key")
        self.lookup.assert_not_called()

    def test_failed_force_preserves_old_valid_bytes_and_other_slots_succeed(self):
        game_id = self.add()
        artwork.refresh_artwork()
        old = artwork._path(game_id, "banner").read_bytes()
        self.lutris_download.side_effect = lambda url, kind: b"invalid" if kind == "banner" else self.image
        result = artwork.refresh_artwork(force=True)[game_id]
        self.assertEqual(result.updated_kinds, ("cover", "icon"))
        self.assertEqual(artwork._path(game_id, "banner").read_bytes(), old)
        self.steam_download.assert_not_called()

    def test_freshness_and_provenance_interruption_retries(self):
        game_id = self.add()
        artwork.refresh_artwork()
        self.lutris_download.reset_mock()
        artwork.refresh_artwork()
        self.lutris_download.assert_not_called()
        snapshot = dict(self.row(game_id), _source="lutris")
        atomic = artwork._atomic_write
        count = 0

        def interrupted(path, data):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("interrupted metadata publication")
            atomic(path, data)

        with patch.object(artwork, "_atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError):
                artwork._publish(snapshot, "banner", self.image_bytes("blue"))
        self.assertNotIn("banner", artwork._read_provenance(game_id))
        result = artwork.refresh_artwork()[game_id]
        self.assertEqual(result.updated_kinds, ("banner",))
        metadata = json.loads((artwork._directory(game_id) / "provenance.json").read_text())
        self.assertEqual(metadata["banner"]["source"], "lutris")

    def test_stale_title_source_and_custom_flag_jobs_cannot_publish(self):
        for changes in ({"name": "Renamed"}, {"artwork_source": "steamgriddb"}, {"has_custom_banner": 1}):
            game_id = self.add()
            snapshot = dict(self.row(game_id), _source="lutris")
            games.update_existing(id=game_id, **changes)
            self.assertFalse(artwork._publish(snapshot, "banner", self.image))
            self.assertFalse(artwork._path(game_id, "banner").exists())
        game_id = self.add()
        snapshot = dict(self.row(game_id), _source="lutris")
        self.values["artwork_source"] = "steamgriddb"
        self.assertFalse(artwork._publish(snapshot, "icon", self.image))

    def test_custom_save_and_reset_failure_preserve_manual_artwork(self):
        game_id = self.add()
        file = self.root / "manual.png"
        file.write_bytes(self.image)
        artwork.save_custom_artwork(game_id, "banner", str(file))
        original = artwork._path(game_id, "banner", True).read_bytes()
        self.assertTrue(self.row(game_id)["has_custom_banner"])
        self.lutris_download.return_value = None
        self.assertEqual(artwork.reset_custom_artwork(game_id, "banner").status, "error")
        self.assertEqual(artwork._path(game_id, "banner", True).read_bytes(), original)
        self.assertTrue(self.row(game_id)["has_custom_banner"])
        self.lutris_download.return_value = self.image
        self.assertEqual(artwork.reset_custom_artwork(game_id, "banner").status, "success")
        self.assertFalse(self.row(game_id)["has_custom_banner"])
        self.assertEqual(artwork._path(game_id, "banner", True).read_bytes(), original)

    def test_invalid_custom_file_does_not_set_flag(self):
        game_id = self.add()
        path = self.root / "invalid.png"
        path.write_bytes(b"bad")
        with self.assertRaises(ValueError):
            artwork.save_custom_artwork(game_id, "icon", str(path))
        self.assertFalse(self.row(game_id)["has_custom_icon"])

    def test_private_candidates_preserve_legacy_without_custom_auto_fallthrough(self):
        game_id = self.add(has_custom_banner=1)
        paths = artwork.get_game_media_paths(self.row(game_id), LutrisBanner())
        self.assertIn("/custom/banner.jpg", paths[0].path)
        self.assertEqual(
            [item.path for item in paths[1:]], [item.path for item in LutrisBanner().get_possible_media_paths("same")]
        )
        self.assertFalse(any("/auto/" in item.path for item in paths))
        paths = artwork.get_game_media_paths(self.row(game_id), LutrisCoverart())
        self.assertIn("/auto/cover.jpg", paths[0].path)

    def test_explicit_role_preserves_incoming_service_media_and_size(self):
        from lutris.services.steam import SteamBanner

        game_id = self.add()
        media = SteamBanner()
        paths = artwork.get_game_media_paths(self.row(game_id), media, kind="banner")
        self.assertIn("/auto/banner.jpg", paths[0].path)
        self.assertIs(paths[0].service_media, media)
        self.assertEqual(paths[0].size, media.size)
        unknown = artwork.get_game_media_paths(self.row(game_id), media, kind="unknown")
        self.assertEqual(
            [item.path for item in unknown], [item.path for item in media.get_possible_media_paths("same")]
        )

    def test_forced_all_custom_validates_title_but_never_downloads(self):
        game_id = self.add(
            artwork_source="steamgriddb", has_custom_banner=1, has_custom_icon=1, has_custom_coverart_big=1
        )
        artwork.refresh_artwork()
        self.lookup.assert_not_called()
        for status in ("no_match", "ambiguous", "success"):
            self.lookup.return_value = ArtworkLookup(status, {"banner": "banner"})
            self.assertEqual(artwork.refresh_artwork(force=True)[game_id].status, status)
        self.values["steamgriddb_api_key"] = ""
        self.assertEqual(artwork.refresh_artwork(force=True)[game_id].status, "missing_key")
        self.steam_download.assert_not_called()
        self.assertFalse(artwork._directory(game_id).exists())

    def test_deleted_game_and_invalid_ids_cannot_publish(self):
        game_id = self.add()
        snapshot = dict(self.row(game_id), _source="lutris")
        from lutris.database import sql

        sql.db_delete(settings.DB_PATH, "games", "id", game_id)
        self.assertFalse(artwork._publish(snapshot, "banner", self.image))
        for invalid in ("0", "-1", "../1", "1/2", "١"):
            with self.subTest(game_id=invalid), self.assertRaises(ValueError):
                artwork._directory(invalid)

    def test_manual_publication_failure_never_sets_flag(self):
        game_id = self.add()
        path = self.root / "manual.png"
        path.write_bytes(self.image)
        with patch.object(artwork, "_atomic_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                artwork.save_custom_artwork(game_id, "banner", str(path))
        self.assertFalse(self.row(game_id)["has_custom_banner"])

    def test_authentication_stop_prevents_more_steam_requests(self):
        first = self.add(artwork_source="steamgriddb")
        second = self.add(artwork_source="steamgriddb")
        self.lookup.side_effect = artwork.steamgriddb._StopBatch("rejected")
        results = artwork.refresh_artwork()
        self.assertEqual(results[first].status, "error")
        self.assertEqual(results[second].status, "error")
        self.lookup.assert_called_once()
        self.api_games.assert_not_called()

    def test_asset_batch_stop_retains_successful_publication_counts(self):
        game_id = self.add(artwork_source="steamgriddb")
        self.steam_download.side_effect = [self.image, artwork.steamgriddb._StopBatch("rate limited")]
        result = artwork.refresh_artwork()[game_id]
        self.assertEqual(result.updated_kinds, ("banner",))
        self.assertTrue(artwork._path(game_id, "banner").exists())

    def test_lutris_aliases_share_lookup_without_title_guessing(self):
        self.api_games.return_value = [
            {"slug": "canonical", "aliases": [{"slug": "same"}], "banner": "https://lutris.net/banner.jpg"}
        ]
        game_id = self.add()
        self.assertEqual(artwork.refresh_artwork()[game_id].updated_kinds, ("banner",))

    def test_lutris_download_rejects_untrusted_urls_and_uses_no_auth(self):
        from types import SimpleNamespace

        with (
            patch.object(artwork, "_download_lutris", self.original_lutris_download),
            patch.object(artwork.steamgriddb, "_Request") as request,
        ):
            request.return_value.get.return_value = SimpleNamespace(status_code=200, content=self.image)
            self.assertTrue(artwork._download_lutris("https://images.igdb.com/cover.jpg", "cover"))
            request.assert_called_once_with("https://images.igdb.com/cover.jpg")
            for url in (
                "file:///etc/passwd",
                "https://evil.example/image",
                "https://user@lutris.net/image",
                "https://lutris.net/%2e%2e/image",
            ):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    artwork._download_lutris(url, "cover")
