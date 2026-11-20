import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lutris.services.gog import GOGService

DB_GAME = {
    "service_id": "1627372090",
    "runner": "wine",
    "directory": "/games/control",
    "name": "CONTROL Resonant",
    "installer_slug": "control_resonant",
    "slug": "control-resonant",
}


class TestDepotUpdateInstallers(unittest.TestCase):
    def get_installers(self, installed_ids):
        with (
            patch("lutris.util.gogdl.is_depot_installed", return_value=True),
            patch("lutris.util.gog.find_installed_product_ids", return_value=installed_ids),
        ):
            return GOGService().get_update_installers(DB_GAME)

    def test_offers_update_then_repair(self):
        installers = self.get_installers({"1627372090"})
        steps = [installer["script"]["installer"][0]["gogdl_setup"] for installer in installers]
        self.assertEqual([step["command"] for step in steps], ["update", "repair"])
        self.assertTrue(all("dlcs" not in step for step in steps))
        # The installer window picks the chosen script by version, so they must differ
        self.assertEqual(len({installer["version"] for installer in installers}), 2)

    def test_repair_covers_installed_dlcs(self):
        installers = self.get_installers({"1627372090", "2", "1"})
        for installer in installers:
            self.assertEqual(installer["script"]["installer"][0]["gogdl_setup"]["dlcs"], "1,2")


def make_patch(name, version, os_name="windows", language="en", size=1000):
    return {"name": name, "version": version, "os": os_name, "language": language, "total_size": size}


# Shaped like real GOG data: multi-part patches share a name, different patches can share a
# version, versions can be blank, and some patches come in several languages.
PATCHES = [
    make_patch("Patch (2.31a to 2.5)", "2.5"),
    make_patch("Patch (2.31a to 2.5)", "2.5"),
    make_patch("32Bit Installer", "2.5"),
    make_patch("Patch 2.12", "2.12", language="de"),
    make_patch("Patch 2.12", "2.12", language="en"),
    make_patch("Patch 2.1.63.2 (gog-4)", "", os_name="linux"),
    make_patch("Patch 2.2.66.0 (gog-5)", "", os_name="linux"),
    make_patch("Original version for Mac OS X", "1.0.0", os_name="mac"),
]


class TestPatchUpdateInstallers(unittest.TestCase):
    """Games installed from the offline installers are updated from GOG's patch files"""

    def setUp(self):
        self.service = GOGService()
        details_patch = patch.object(self.service, "get_game_details", return_value={"downloads": {"patches": PATCHES}})
        language_patch = patch("lutris.services.gog.i18n.get_lang", return_value="en")
        depot_patch = patch("lutris.util.gogdl.is_depot_installed", return_value=False)
        for mock_patch in (details_patch, language_patch, depot_patch):
            mock_patch.start()
            self.addCleanup(mock_patch.stop)

    def get_installers(self, runner):
        installers = self.service.get_update_installers({**DB_GAME, "runner": runner})
        return {installer["version"]: installer for installer in installers}

    def get_patch_parts(self, installer):
        installer_info = SimpleNamespace(
            service_appid=DB_GAME["service_id"], runner=installer["runner"], version=installer["version"]
        )
        with (
            patch.object(self.service, "query_download_links", side_effect=lambda part: [part]),
            patch.object(self.service, "_format_links", side_effect=lambda _installer, _file_id, links: links),
        ):
            return self.service.get_patch_files(installer_info, "gogpatch")

    def test_windows_patches_run_in_wine(self):
        installers = self.get_installers("wine")
        self.assertEqual(set(installers), {"GOG Patch (2.31a to 2.5)", "GOG 32Bit Installer", "GOG Patch 2.12"})
        for installer in installers.values():
            self.assertEqual(installer["runner"], "wine")
            self.assertEqual(installer["script"]["installer"][0]["task"]["name"], "wineexec")

    def test_linux_patches_are_extracted_into_the_game(self):
        installers = self.get_installers("linux")
        # Their versions are blank, so they must still get distinct installers
        self.assertEqual(set(installers), {"GOG Patch 2.1.63.2 (gog-4)", "GOG Patch 2.2.66.0 (gog-5)"})
        for installer in installers.values():
            self.assertEqual(installer["runner"], "linux")
            steps = [next(iter(step)) for step in installer["script"]["installer"]]
            self.assertEqual(steps, ["extract", "merge"])

    def test_patch_files_are_all_parts_of_the_chosen_patch(self):
        installers = self.get_installers("wine")
        parts = self.get_patch_parts(installers["GOG Patch (2.31a to 2.5)"])
        self.assertEqual([part["name"] for part in parts], ["Patch (2.31a to 2.5)"] * 2)

    def test_patch_files_are_in_one_language(self):
        installers = self.get_installers("wine")
        parts = self.get_patch_parts(installers["GOG Patch 2.12"])
        self.assertEqual([part["language"] for part in parts], ["en"])

    def test_linux_patch_files_are_just_the_chosen_patch(self):
        installers = self.get_installers("linux")
        parts = self.get_patch_parts(installers["GOG Patch 2.2.66.0 (gog-5)"])
        self.assertEqual([part["name"] for part in parts], ["Patch 2.2.66.0 (gog-5)"])
