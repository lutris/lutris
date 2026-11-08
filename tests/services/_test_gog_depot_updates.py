import unittest
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
