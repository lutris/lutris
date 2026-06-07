from unittest import TestCase

from lutris.gui.views.all_sources import get_service_view_id, get_unmatched_local_games, parse_service_view_id


class TestServiceViewId(TestCase):
    def test_round_trip(self):
        view_id = get_service_view_id("steam", "12345")
        self.assertEqual(view_id, "service:steam:12345")
        self.assertEqual(parse_service_view_id(view_id), ("steam", "12345"))

    def test_round_trip_preserves_colons_in_appid(self):
        view_id = get_service_view_id("steam", "a:b:c")
        self.assertEqual(parse_service_view_id(view_id), ("steam", "a:b:c"))

    def test_non_service_ids_are_rejected(self):
        self.assertEqual(parse_service_view_id("42"), (None, None))
        self.assertEqual(parse_service_view_id(42), (None, None))
        self.assertEqual(parse_service_view_id("some-game-slug"), (None, None))
        self.assertEqual(parse_service_view_id(""), (None, None))

    def test_malformed_service_ids_are_rejected(self):
        self.assertEqual(parse_service_view_id("service"), (None, None))
        self.assertEqual(parse_service_view_id("service:steam"), (None, None))
        self.assertEqual(parse_service_view_id("services:steam:1234"), (None, None))


class TestGetUnmatchedLocalGames(TestCase):
    def test_local_game_matched_by_service_is_removed(self):
        local_games = [{"name": "Foo", "service": "steam", "service_id": "1234"}]
        self.assertEqual(get_unmatched_local_games(local_games, {"steam": {"1234"}}), [])

    def test_local_game_with_unmatched_appid_is_kept(self):
        local_games = [{"name": "Foo", "service": "steam", "service_id": "1234"}]
        self.assertEqual(get_unmatched_local_games(local_games, {"steam": {"5678"}}), local_games)

    def test_local_game_of_unknown_service_is_kept(self):
        local_games = [{"name": "Foo", "service": "gog", "service_id": "1234"}]
        self.assertEqual(get_unmatched_local_games(local_games, {"steam": {"1234"}}), local_games)

    def test_local_game_without_service_is_kept(self):
        local_games = [{"name": "Foo"}]
        self.assertEqual(get_unmatched_local_games(local_games, {"steam": {"1234"}}), local_games)

    def test_failed_service_with_empty_appid_set_keeps_local_games(self):
        # A service whose games could not be loaded contributes an empty set,
        # which must keep its local copies visible (fail soft).
        local_games = [{"name": "Foo", "service": "steam", "service_id": "1234"}]
        self.assertEqual(get_unmatched_local_games(local_games, {"steam": set()}), local_games)

    def test_mixed_games_are_filtered_correctly(self):
        matched = {"name": "Matched", "service": "steam", "service_id": "1"}
        unmatched = {"name": "Unmatched", "service": "steam", "service_id": "2"}
        no_service = {"name": "Local only"}
        result = get_unmatched_local_games([matched, unmatched, no_service], {"steam": {"1"}})
        self.assertEqual(result, [unmatched, no_service])
