from unittest import TestCase

from lutris.util.ubisoft.parser import UbisoftParser


class TestUbisoftParser(TestCase):
    def setUp(self):
        self.parser = UbisoftParser()

    def test_get_field_from_yaml_with_null_name(self):
        game_yaml = {"root": {"name": None, "installer": {"game_identifier": "Some Game"}}}
        self.assertEqual(self.parser._get_field_from_yaml(game_yaml, "name"), "Some Game")

    def test_get_field_from_yaml_with_missing_thumb_image(self):
        game_yaml = {"root": {"name": "Some Game"}}
        self.assertEqual(self.parser._get_field_from_yaml(game_yaml, "thumb_image"), "")
