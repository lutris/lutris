from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
from unittest.mock import PropertyMock, patch

from lutris import settings
from lutris.config import write_game_config
from lutris.database import categories, games, schema, sql
from lutris.game import Game
from lutris.services.steam import SteamGame, SteamService
from lutris.util.steam.appmanifest import APP_STATE_FLAGS

APPID = "12345"
FULLY_INSTALLED = 1 << (APP_STATE_FLAGS.index("Fully Installed") - 1)
# With playtime, so the dedup at the end of add_installed_games() keeps the entry
PLAYTIME = 1.0
APPMANIFEST = dedent(
    """\
    "AppState"
    {
        "appid"       "%s"
        "name"        "Test Game"
        "StateFlags"  "%s"
    }
    """
)


class TestImportInstalledSteamGames(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        for name, value in {"DB_PATH": str(self.directory / "pga.db"), "CONFIG_DIR": str(self.directory)}.items():
            patcher = patch.object(settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        schema.syncdb()
        (self.directory / "games").mkdir()
        self.steamapps = self.directory / "steamapps"
        self.steamapps.mkdir()
        SteamGame.new_from_steam_game({"appid": APPID, "name": "Test Game"}).save()
        for patcher in (
            patch.object(
                SteamService, "steamapps_paths", new_callable=PropertyMock, return_value=[str(self.steamapps)]
            ),
            # Don't touch the real desktop and Steam shortcuts when uninstalling
            patch("lutris.game.remove_steam_shortcut"),
            patch("lutris.game.xdgshortcuts.remove_launcher"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch("lutris.services.steam.sync_media")
        self.sync_media = patcher.start()
        self.addCleanup(patcher.stop)

    def set_installed_in_steam(self, installed):
        manifest = self.steamapps / ("appmanifest_%s.acf" % APPID)
        if installed:
            manifest.write_text(APPMANIFEST % (APPID, FULLY_INSTALLED), encoding="utf-8")
        else:
            manifest.unlink()

    def get_imported_games(self):
        return games.get_games(filters={"service": "steam", "service_id": APPID})

    def test_installed_game_is_imported_once(self):
        self.set_installed_in_steam(True)
        service = SteamService()
        service.add_installed_games()
        service.add_installed_games()

        imported = self.get_imported_games()
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0]["installed"], 1)
        self.assertEqual(Game(imported[0]["id"]).config.game_level["game"]["appid"], APPID)

    def test_game_reinstalled_in_steam_is_installed_again(self):
        service = SteamService()
        self.set_installed_in_steam(True)
        service.add_installed_games()
        self.set_installed_in_steam(False)
        service.add_installed_games()
        self.assertEqual(self.get_imported_games()[0]["installed"], 0)

        self.set_installed_in_steam(True)
        service.add_installed_games()

        imported = self.get_imported_games()
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0]["installed"], 1)
        self.assertEqual(imported[0]["runner"], "steam")
        game = Game(imported[0]["id"])
        self.assertTrue(game.is_installed)
        self.assertEqual(game.config.game_level["game"]["appid"], APPID)

    def test_reinstall_keeps_what_was_changed_in_lutris(self):
        service = SteamService()
        self.set_installed_in_steam(True)
        service.add_installed_games()
        self.set_installed_in_steam(False)
        service.add_installed_games()
        game_id = self.get_imported_games()[0]["id"]
        sql.db_update(
            settings.DB_PATH,
            "games",
            {"name": "Renamed Game", "slug": "renamed-game", "installed_at": None},
            {"id": game_id},
        )
        categories.add_game_to_category(game_id, categories.add_category("Shooters"))

        self.set_installed_in_steam(True)
        service.add_installed_games()

        game = games.get_game_by_field(game_id, "id")
        self.assertEqual(game["installed"], 1)
        self.assertEqual(game["name"], "Renamed Game")
        self.assertEqual(game["slug"], "renamed-game")
        self.assertIsNotNone(game["installed_at"])
        self.assertEqual(categories.get_categories_in_game(game_id), ["Shooters"])
        self.assertEqual(self.sync_media.call_args.args[0], ["renamed-game"])

    def test_uninstalled_duplicate_is_left_alone_when_another_entry_is_installed(self):
        entry = {"name": "Test Game", "installer_slug": "steam-%s" % APPID, "service": "steam", "service_id": APPID}
        uninstalled_id = games.add_game(slug="test-game", installed=0, **entry)
        configpath = write_game_config("steam-%s" % APPID, {"game": {"appid": APPID}})
        installed_id = games.add_game(
            slug="test-game-2", installed=1, runner="steam", configpath=configpath, playtime=PLAYTIME, **entry
        )
        self.set_installed_in_steam(True)

        SteamService().add_installed_games()

        uninstalled = games.get_game_by_field(uninstalled_id, "id")
        self.assertIsNotNone(uninstalled)
        self.assertEqual(uninstalled["installed"], 0)
        self.assertEqual(games.get_game_by_field(installed_id, "id")["installed"], 1)
