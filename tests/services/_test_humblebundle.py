"""Tests for the installers generated for Humble Bundle games."""

import json
import unittest

from lutris.services.humblebundle import HumbleBundleService


def make_download(platform, filename):
    return {
        "platform": platform,
        "download_struct": [
            {"name": "Download", "url": {"web": "https://dl.humble.com/%s?gamekey=abc" % filename}},
        ],
    }


def make_db_game(*downloads):
    details = {"machine_name": "anomalywarzoneearth", "downloads": list(downloads)}
    return {
        "name": "Anomaly Warzone Earth",
        "slug": "anomaly-warzone-earth",
        "appid": "anomalywarzoneearth",
        "details": json.dumps(details),
    }


class TestGenerateInstallers(unittest.TestCase):
    def setUp(self):
        self.service = HumbleBundleService()

    def test_linux_and_windows_builds_are_both_offered(self):
        db_game = make_db_game(
            make_download("linux", "AnomalyWarzoneEarth-Installer_Humble_Linux.zip"),
            make_download("windows", "AnomalyWarzoneEarth-Setup.exe"),
        )

        installers = self.service.generate_installers(db_game)

        self.assertEqual([installer["runner"] for installer in installers], ["linux", "wine"])
        self.assertEqual(len({installer["version"] for installer in installers}), 2)

    def test_default_installer_prefers_linux(self):
        db_game = make_db_game(
            make_download("windows", "AnomalyWarzoneEarth-Setup.exe"),
            make_download("linux", "AnomalyWarzoneEarth-Installer_Humble_Linux.zip"),
        )

        self.assertEqual(self.service.generate_installer(db_game)["runner"], "linux")

    def test_windows_only_game_gets_a_wine_installer(self):
        db_game = make_db_game(make_download("windows", "Game-Setup.exe"))

        installers = self.service.generate_installers(db_game)

        self.assertEqual([installer["runner"] for installer in installers], ["wine"])
        self.assertEqual(installers[0]["version"], "Humble Bundle")

    def test_platform_without_files_is_skipped(self):
        empty_linux = {"platform": "linux", "download_struct": []}
        db_game = make_db_game(empty_linux, make_download("windows", "Game-Setup.exe"))

        installers = self.service.generate_installers(db_game)

        self.assertEqual([installer["runner"] for installer in installers], ["wine"])

    def test_unsupported_platforms_give_no_installer(self):
        db_game = make_db_game(make_download("mac", "Game.dmg"))

        self.assertEqual(self.service.generate_installers(db_game), [])
        self.assertEqual(self.service.generate_installer(db_game), {})
