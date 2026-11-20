"""Tests for the itch.io service."""

import os
import tempfile
import unittest
from unittest.mock import patch

from lutris.services.itchio import ItchIoService

PAID_GAME = {"id": 1234, "title": "Paid Game", "traits": ["can_be_bought", "p_linux"], "min_price": 500}
DOWNLOAD_KEY_ID = 98765


class TestGetKey(unittest.TestCase):
    """A game bought after the library was last loaded has no download key in the cache."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        cache_patch = patch.multiple(
            ItchIoService,
            cache_path=temp_dir.name,
            games_cache_path=os.path.join(temp_dir.name, "games/"),
            key_cache_file=os.path.join(temp_dir.name, "profile/owned-keys.json"),
        )
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        self.service = ItchIoService()

    def test_newly_bought_game_finds_its_key(self):
        owned_keys = {"owned_keys": [{"id": DOWNLOAD_KEY_ID, "game": dict(PAID_GAME)}], "per_page": 50}
        with (
            patch.object(self.service, "fetch_game", return_value={"game": dict(PAID_GAME)}),
            patch.object(self.service, "fetch_owned_keys", return_value=owned_keys),
        ):
            # Lutris keeps itch.io IDs as strings; the API gives them as numbers
            self.assertEqual(self.service.get_key(str(PAID_GAME["id"])), DOWNLOAD_KEY_ID)


class TestApiKey(unittest.TestCase):
    def test_saved_key_loses_surrounding_whitespace(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        key_path = os.path.join(temp_dir.name, "api-key")
        with open(key_path, "w", encoding="utf-8") as key_file:
            key_file.write(" abc123\n")
        with patch.object(ItchIoService, "api_key_path", key_path):
            self.assertEqual(ItchIoService().get_headers(), {"Authorization": "Bearer abc123"})
