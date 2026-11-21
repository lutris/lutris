from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from lutris import settings
from lutris.database import schema
from lutris.database.services import ServiceGameCollection
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame


class FakeGame(ServiceGame):
    service = "fake"

    def __init__(self, appid, name):
        super().__init__()
        self.appid = appid
        self.name = name
        self.slug = name.lower()
        self.details = "{}"


class OtherGame(FakeGame):
    service = "other"


class FakeService(BaseService):
    id = "fake"
    name = "Fake"

    def __init__(self, games, error=None):
        self.games_to_load = games
        self.error = error

    def load(self):
        # Like the real services, save games as they come in, so a failure leaves a partial library
        for game in self.games_to_load:
            game.save()
            if self.error:
                raise self.error

    def load_icons(self):
        pass

    def add_installed_games(self):
        pass


class TestServiceReload(TestCase):
    """A failed reload must keep the previously synced library; a successful one replaces it"""

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(settings, "DB_PATH", str(Path(directory.name) / "pga.db"))
        patcher.start()
        self.addCleanup(patcher.stop)
        schema.syncdb()

        FakeGame("1", "Old One").save()
        FakeGame("2", "Old Two").save()
        # A game belonging to another service must never be touched by a reload
        OtherGame("3", "Other Service Game").save()
        self.previous = ServiceGameCollection.get_for_service("fake")
        self.assertEqual(len(self.previous), 2)

        self.loading = self._patch_signal("SERVICE_GAMES_LOADING")
        self.loaded = self._patch_signal("SERVICE_GAMES_LOADED")

        # Run the reload synchronously, the way AsyncCall would on its worker thread
        def run_sync(function, callback):
            try:
                result, error = function(), None
            except Exception as ex:
                result, error = None, ex
            callback(result, error)

        patcher = patch("lutris.services.base.AsyncCall", side_effect=run_sync)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch_signal(self, name):
        patcher = patch("lutris.services.base." + name)
        signal = patcher.start()
        self.addCleanup(patcher.stop)
        return signal

    @staticmethod
    def without_ids(service):
        games = ServiceGameCollection.get_for_service(service)
        return [dict(game, id=None) for game in sorted(games, key=lambda game: game["appid"])]

    def reload(self, service):
        reloaded_callback = Mock()
        service.start_reload(reloaded_callback)
        self.assertEqual(reloaded_callback.call_count, 1)
        self.loading.fire.assert_called_once_with(service)
        self.loaded.fire.assert_called_once_with(service)
        return reloaded_callback.call_args.args[0]

    def test_failed_load_keeps_previous_games(self):
        error = RuntimeError("Failed to load games")
        # The failing load saves a new game first, which must not survive either
        service = FakeService([FakeGame("9", "Partial")], error=error)

        self.assertIs(self.reload(service), error)

        # The restored rows are the same, apart from their ids
        self.assertEqual(
            self.without_ids("fake"),
            [dict(game, id=None) for game in sorted(self.previous, key=lambda game: game["appid"])],
        )
        self.assertEqual(len(ServiceGameCollection.get_for_service("other")), 1)
        self.assertFalse(service.is_loading)

    def test_successful_load_replaces_previous_games(self):
        service = FakeService([FakeGame("2", "Old Two"), FakeGame("4", "New Four")])

        self.assertIsNone(self.reload(service))

        self.assertCountEqual([game["appid"] for game in ServiceGameCollection.get_for_service("fake")], ["2", "4"])
        self.assertEqual(len(ServiceGameCollection.get_for_service("other")), 1)
