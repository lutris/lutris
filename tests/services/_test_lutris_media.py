from unittest import TestCase
from unittest.mock import patch

from lutris.artwork import RefreshResult
from lutris.services import lutris


class TestMediaIntegration(TestCase):
    def setUp(self):
        self.rows = [{"id": "1", "slug": "same"}, {"id": "2", "slug": "same"}, {"id": "3", "slug": "other"}]

    def test_slug_iterables_select_every_matching_row_and_aggregate_counts(self):
        for slugs, ids in ((None, ["1", "2", "3"]), (iter(["same"]), ["1", "2"]), ([], [])):
            with (
                self.subTest(slugs=slugs),
                patch.object(lutris, "get_games", return_value=self.rows),
                patch(
                    "lutris.artwork.refresh_artwork",
                    return_value={
                        "1": RefreshResult("success", ("banner", "icon"), "1", "Game", "lutris"),
                        "2": RefreshResult("success", ("banner", "cover"), "2", "Game", "steamgriddb"),
                    },
                ) as refresh,
            ):
                result = lutris.sync_media(slugs)
                if ids:
                    refresh.assert_called_once_with(ids)
                    self.assertEqual(result, {"banners": 2, "icons": 1, "covers": 1})
                else:
                    refresh.assert_not_called()
                    self.assertEqual(result, {})

    def test_single_slug_routes_all_rows_without_legacy_download(self):
        with (
            patch.object(lutris, "get_games", return_value=self.rows),
            patch("lutris.artwork.refresh_artwork") as refresh,
            patch.object(lutris, "_download_lutris_media") as legacy,
        ):
            self.assertIsNone(lutris.download_lutris_media("same"))
            refresh.assert_called_once_with(["1", "2"])
            legacy.assert_not_called()

    def test_remote_only_artwork_never_guesses_title_for_steamgriddb(self):
        for source in ("lutris", "steamgriddb"):
            with (
                self.subTest(source=source),
                patch.object(lutris, "get_games", return_value=[]),
                patch("lutris.artwork.settings.read_setting", return_value=source),
                patch.object(lutris, "_download_lutris_media") as legacy,
            ):
                lutris.download_lutris_media("remote")
                self.assertEqual(legacy.call_count, int(source == "lutris"))
