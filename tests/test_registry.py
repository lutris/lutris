import os
from unittest import TestCase
from lutris.util.wineregistry import WineRegistry

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), 'fixtures')


class TestWineRegistry(TestCase):
    def setUp(self):
        registry_path = os.path.join(FIXTURES_PATH, 'user.reg')
        self.registry = WineRegistry(registry_path)

    def test_can_load_registry(self):
        self.assertTrue(len(self.registry.keys) > 10)

    def test_can_query_registry(self):
        value = self.registry.query('Control Panel/Keyboard', 'KeyboardSpeed')
        self.assertEqual(value, '31')

    def test_can_get_timestamp_as_int(self):
        key = self.registry.get_key('Control Panel/Keyboard')
        self.assertEqual(key.timestamp, 1477412318)

    def test_can_get_timestamp_as_float(self):
        key = self.registry.get_key('Control Panel/Sound')
        self.assertEqual(key.timestamp, 1475423303.7943190)

    def test_can_get_meta(self):
        key = self.registry.get_key('Control Panel/Sound')
        self.assertEqual(key.get_meta('time'), '1d21cc468677196')
