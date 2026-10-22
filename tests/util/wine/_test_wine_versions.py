"""Tests for the list of Wine versions offered in the Wine version dropdown."""

import unittest
from unittest.mock import patch

from lutris.util.wine import proton, wine
from lutris.util.wine.wine import GE_PROTON_LATEST, get_installed_wine_versions

PROTON_VERSIONS = ["GE-Proton10-25", "GE-Proton10-9", "GE-Proton9-27"]
LUTRIS_VERSIONS = ["wine-ge-8-26-x86_64", "lutris-7.2-2-x86_64", "lutris-GE-Proton8-26-x86_64"]
SYSTEM_VERSIONS = ["winehq-staging", "system"]


class TestInstalledWineVersions(unittest.TestCase):
    def get_versions(self, proton_versions, lutris_versions, system_versions):
        get_installed_wine_versions.cache_clear()
        try:
            with (
                patch.object(proton, "list_proton_versions", return_value=proton_versions),
                patch.object(wine, "list_lutris_wine_versions", return_value=lutris_versions),
                patch.object(wine, "list_system_wine_versions", return_value=system_versions),
            ):
                return get_installed_wine_versions()
        finally:
            get_installed_wine_versions.cache_clear()

    def test_versions_keep_their_presentation_order(self):
        versions = self.get_versions(PROTON_VERSIONS, LUTRIS_VERSIONS, SYSTEM_VERSIONS)
        self.assertEqual(versions, [GE_PROTON_LATEST, *PROTON_VERSIONS, *LUTRIS_VERSIONS, *SYSTEM_VERSIONS])

    def test_duplicates_are_listed_once_where_first_seen(self):
        versions = self.get_versions(["GE-Proton10-25"], ["GE-Proton10-25", "lutris-7.2-2-x86_64"], [])
        self.assertEqual(versions, [GE_PROTON_LATEST, "GE-Proton10-25", "lutris-7.2-2-x86_64"])
