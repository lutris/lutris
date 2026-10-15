import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database import games, schema
from lutris.services.egs import EGSGame, EpicGamesStoreService
from lutris.util.egs.egs_launcher import EGSLauncher


class TestImportInstalledEGSGames(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        for name, value in {"DB_PATH": str(self.directory / "pga.db"), "CONFIG_DIR": str(self.directory)}.items():
            patcher = patch.object(settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        schema.syncdb()
        self.assertTrue((self.directory / "pga.db").is_file())
        (self.directory / "games").mkdir()
        self.prefix = self.directory / "prefix"
        self.manifests_path = self.prefix / "drive_c" / EGSLauncher.manifests_paths
        self.manifests_path.mkdir(parents=True)
        configpath = write_game_config("epic-games-store", {"game": {"exe": "EpicGamesLauncher.exe"}, "wine": {}})
        games.add_game(
            name="Epic Games Store",
            slug="epic-games-store",
            runner="wine",
            directory=str(self.prefix / "drive_c" / "Epic Games"),
            configpath=configpath,
        )

    def test_empty_parent_base_game_is_imported_once_and_dlc_is_not_imported(self):
        for app_name, title, parent in (
            ("base-game", "Base Game", ""),
            ("matching-game", "Matching Game", "matching-game"),
            ("dlc", "DLC", "base-game"),
        ):
            EGSGame.new_from_api(
                {"appName": app_name, "title": title, "namespace": "namespace", "catalogItemId": app_name + "-item"}
            ).save()
            manifest = {"AppName": app_name, "MainGameAppName": parent}
            (self.manifests_path / (app_name + ".item")).write_text(json.dumps(manifest), encoding="utf-8")

        with patch("lutris.services.egs.sync_media") as sync_media:
            service = EpicGamesStoreService()
            service.add_installed_games()
            self.assertCountEqual(sync_media.call_args.args[0], ["base-game", "matching-game"])
            imported = games.get_games(filters={"service": "egs"})
            service.add_installed_games()
            self.assertEqual(sync_media.call_args.args[0], [])
            self.assertEqual(games.get_games(filters={"service": "egs"}), imported)

        self.assertCountEqual([game["service_id"] for game in imported], ["base-game", "matching-game"])
        for game in imported:
            with self.subTest(app_name=game["service_id"]):
                self.assertEqual(game["installed"], 1)
                self.assertEqual(game["runner"], "wine")
                self.assertTrue((self.directory / "games" / (game["configpath"] + ".yml")).is_file())
                config = LutrisConfig(game_config_id=game["configpath"]).game_level
                self.assertEqual(config["game"]["exe"], "EpicGamesLauncher.exe")
                self.assertIn(
                    f"namespace%3A{game['service_id']}-item%3A{game['service_id']}?action=launch",
                    config["game"]["args"],
                )
