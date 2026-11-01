from unittest import TestCase
from unittest.mock import patch

from lutris.gui import game_source
from lutris.gui.game_filter import FilterValues
from lutris.gui.game_source import GameSourceContext, ViewSortSettings
from lutris.search import GameSearch


def make_context(filters=None, service=None, sorting="name", running_ids=None) -> GameSourceContext:
    filters = filters or {}
    return GameSourceContext(
        filters=FilterValues(filters),
        search=GameSearch(filters.get("text", ""), service),
        service=service,
        sort_settings=ViewSortSettings(sorting, False, True),
        running_ids=running_ids or (lambda: []),
    )


class TestCombineGames(TestCase):
    def test_lutris_data_is_injected_into_a_matching_service_game(self):
        service_game = {"appid": "a", "name": "A"}
        lutris_game = {
            "service_id": "a",
            "platform": "Linux",
            "runner": "linux",
            "installed_at": 1,
            "lastplayed": 2,
            "playtime": 3,
            "installed": True,
            "year": "2001",
        }
        result = game_source.combine_games(service_game, lutris_game)
        self.assertEqual(result["platform"], "Linux")
        self.assertEqual(result["installed"], True)
        self.assertEqual(result["year"], "2001")

    def test_non_matching_game_is_left_alone(self):
        result = game_source.combine_games({"appid": "b", "name": "B"}, {"service_id": "a"})
        self.assertNotIn("platform", result)

    def test_missing_lutris_game_is_left_alone(self):
        self.assertEqual(game_source.combine_games({"appid": "c"}, None), {"appid": "c"})


class TestRecentGames(TestCase):
    def test_recent_games_sort_by_most_recent(self):
        # Category '.hidden' keeps the view search empty, so no database lookups are needed.
        context = make_context({"category": ".hidden"})
        games = [
            {"id": 1, "name": "Old", "installed_at": 100, "lastplayed": 0},
            {"id": 2, "name": "New", "installed_at": 200, "lastplayed": 0},
        ]
        with patch.object(game_source.games_db, "get_games", return_value=games):
            result = game_source.get_recent_games(context)
        self.assertEqual([game["id"] for game in result], [2, 1])


class TestGetGamesFromFilters(TestCase):
    def test_dynamic_category_is_loaded_by_the_matching_function(self):
        context = make_context({"dynamic_category": "running", "category": ".hidden"}, running_ids=lambda: [1, 2])
        with patch.object(game_source.games_db, "get_games_by_ids", return_value=[{"id": 1, "name": "A"}]) as by_ids:
            result = game_source.get_games_from_filters(context)
        by_ids.assert_called_once_with([1, 2])
        self.assertEqual([game["id"] for game in result], [1])

    def test_runner_filter_and_category_membership_are_applied(self):
        context = make_context({"runner": "wine", "category": "all"})
        games = [
            {"id": 1, "name": "A", "installed": True},
            {"id": 3, "name": "C", "installed": True},
        ]
        with (
            patch.object(game_source.games_db, "get_games", return_value=games) as get_games,
            patch.object(game_source.categories_db, "get_game_ids_for_categories", return_value={1, 2}) as get_ids,
            patch.object(game_source.settings, "read_bool_setting", return_value=True),
        ):
            result = game_source.get_games_from_filters(context)
        self.assertEqual([game["id"] for game in result], [1])
        get_games.assert_called_once_with(filters={"runner": "wine"}, excludes={})
        get_ids.assert_called_once_with(None, [".hidden"])

    def test_disabled_services_are_excluded(self):
        context = make_context({"category": "all"})

        def read_setting(key, default=True, section=None):
            return key != "gog_in_games_view"

        with (
            patch.dict(game_source.services.SERVICES, {"gog": object(), "steam": object()}, clear=True),
            patch.object(game_source.games_db, "get_games", return_value=[]) as get_games,
            patch.object(game_source.categories_db, "get_game_ids_for_categories", return_value=set()),
            patch.object(game_source.settings, "read_bool_setting", side_effect=read_setting),
        ):
            game_source.get_games_from_filters(context)
        _args, kwargs = get_games.call_args
        self.assertIn("gog", kwargs["excludes"]["service"])
        self.assertNotIn("steam", kwargs["excludes"]["service"])


class FakeLutrisService:
    id = "lutris"

    def get_game_release_year(self, game):
        return "2001"


class TestGetServiceGames(TestCase):
    def test_service_games_are_combined_with_lutris_data(self):
        context = make_context({"category": ".hidden"}, service=FakeLutrisService())
        service_games = [{"appid": "a", "name": "A", "installed": 0}]
        lutris_games = [
            {
                "slug": "a",
                "service_id": "a",
                "platform": "Linux",
                "runner": "linux",
                "installed_at": 0,
                "lastplayed": 0,
                "playtime": 0,
                "installed": 1,
                "year": "2001",
            }
        ]
        with (
            patch.object(game_source.ServiceGameCollection, "get_for_service", return_value=service_games),
            patch.object(game_source.games_db, "get_games", return_value=lutris_games),
        ):
            result = game_source.get_service_games(context, "lutris")
        self.assertEqual(result[0]["platform"], "Linux")
        self.assertEqual(result[0]["installed"], 1)
