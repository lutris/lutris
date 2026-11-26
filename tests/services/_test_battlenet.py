"""Tests for the Battle.net service."""

import os
import tempfile
from unittest import TestCase

from lutris.services.battlenet import BlizzardProductDbParser
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestBlizzardProductDbParser(TestCase):
    def test_product_db_without_products_has_no_games(self):
        with tempfile.TemporaryDirectory() as prefix:
            product_db_path = prefix + BlizzardProductDbParser.PRODUCT_DB_PATH
            os.makedirs(os.path.dirname(product_db_path))
            with open(product_db_path, "wb"):
                pass

            self.assertEqual(BlizzardProductDbParser(prefix).games, [])
