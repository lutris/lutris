from unittest import TestCase

from lutris.util.resources import parse_installer_url


class TestInstallerUrls(TestCase):
    def test_legacy_url(self):
        result = parse_installer_url("lutris:quake")
        self.assertEqual(result['game_slug'], 'quake')
        self.assertEqual(result['revision'], None)
        self.assertEqual(result['action'], None)

    def test_action_rungameid(self):
        result = parse_installer_url("lutris:rungameid/123")
        self.assertEqual(result['game_slug'], '123')
        self.assertEqual(result['revision'], None)
        self.assertEqual(result['action'], 'rungameid')

    def test_action_rungame(self):
        result = parse_installer_url("lutris:rungame/quake")
        self.assertEqual(result['game_slug'], 'quake')
        self.assertEqual(result['revision'], None)
        self.assertEqual(result['action'], 'rungame')
