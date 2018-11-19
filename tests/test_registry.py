import os
from unittest import TestCase
from lutris.util.wine.registry import WineRegistry, WineRegistryKey

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), 'fixtures')


class TestWineRegistry(TestCase):
    def setUp(self):
        self.registry_path = os.path.join(FIXTURES_PATH, 'user.reg')
        self.registry = WineRegistry(self.registry_path)

    def test_can_load_registry(self):
        self.assertTrue(len(self.registry.keys) > 10)
        self.assertEqual(self.registry.version, 2)
        self.assertEqual(self.registry.arch, 'win64')

    def test_can_query_registry(self):
        value = self.registry.query('Control Panel/Keyboard', 'KeyboardSpeed')
        self.assertEqual(value, '31')

    def test_can_get_timestamp_as_int(self):
        key = self.registry.keys.get('Control Panel/Keyboard')
        self.assertEqual(key.timestamp, 1477412318)

    def test_can_get_timestamp_as_float(self):
        key = self.registry.keys.get('Control Panel/Sound')
        self.assertEqual(key.timestamp, 1475423303.7943190)

    def test_can_get_meta(self):
        key = self.registry.keys.get('Control Panel/Sound')
        self.assertEqual(key.get_meta('time'), '1d21cc468677196')

    def test_can_get_string_value(self):
        key = self.registry.keys.get('Control Panel/Desktop')
        self.assertEqual(key.get_subkey('DragFullWindows'), '0')

    def test_can_get_dword_value(self):
        key = self.registry.keys.get('Control Panel/Desktop')
        self.assertEqual(key.get_subkey('CaretWidth'), 1)

    def test_can_render_key(self):
        expected = (
            '[Software\\\\Wine\\\\Fonts] 1477412318\n'
            '#time=1d22edb71813e3c\n'
            '"Codepages"="1252,437"\n'
            '"LogPixels"=dword:00000000\n'
        )
        key = self.registry.keys.get('Software/Wine/Fonts')
        self.assertEqual(key.render(), expected)

    def test_render_user_reg(self):
        content = self.registry.render()
        with open(self.registry_path, 'r') as registry_file:
            original_content = registry_file.read()
        self.assertEqual(content, original_content)

    def test_can_render_system_reg(self):
        registry_path = os.path.join(FIXTURES_PATH, 'system.reg')
        with open(registry_path, 'r') as registry_file:
            original_content = registry_file.read()
        system_reg = WineRegistry(registry_path)
        content = system_reg.render()
        self.assertEqual(content, original_content)

    def test_can_set_value_to_existing_subkey(self):
        self.assertEqual(self.registry.query('Control Panel/Desktop', 'DragWidth'), '4')
        self.registry.set_value('Control Panel/Desktop', 'DragWidth', '8')
        self.assertEqual(self.registry.query('Control Panel/Desktop', 'DragWidth'), '8')

    def test_can_set_value_to_a_new_sub_key(self):
        self.assertEqual(self.registry.query('Control Panel/Desktop', 'BliBlu'), None)
        self.registry.set_value('Control Panel/Desktop', 'BliBlu', 'yep')
        self.assertEqual(self.registry.query('Control Panel/Desktop', 'BliBlu'), 'yep')

    def test_can_set_value_to_a_new_key(self):
        self.assertEqual(self.registry.query('Wine/DX11', 'FullyWorking'), None)
        self.registry.set_value('Wine/DX11', 'FullyWorking', 'HellYeah')
        self.assertEqual(self.registry.query('Wine/DX11', 'FullyWorking'), 'HellYeah')

    def test_can_clear_a_key(self):
        path = 'Control Panel/Mouse'
        key = self.registry.keys.get(path)
        self.assertEqual(len(key.subkeys), 13)
        self.registry.clear_key(path)
        self.assertEqual(len(key.subkeys), 0)


class TestWineRegistryKey(TestCase):
    def test_creation_by_key_def_parses(self):
        key = WineRegistryKey(key_def='[Control Panel\\\\Desktop] 1477412318')
        self.assertEqual(key.name, 'Control Panel/Desktop')
        self.assertEqual(key.raw_name, '[Control Panel\\\\Desktop]')
        self.assertEqual(key.raw_timestamp, '1477412318')

    def test_creation_by_path_parses(self):
        key = WineRegistryKey(path='Control Panel/Desktop')
        self.assertEqual(key.name, 'Control Panel/Desktop')
        self.assertEqual(key.raw_name, '[Control Panel\\\\Desktop]')
        self.assertRegexpMatches(key.raw_timestamp, r'\d+\s\d+')

    def test_parse_registry_key(self):
        key = WineRegistryKey(path='Control Panel/Desktop')
        key.parse('"C:\\\\users\\\\strider\\\\My Music\\\\iTunes\\\\iTunes Music\\\\Podcasts\\\\"=dword:00000001')
        self.assertEqual(key.subkeys["C:\\\\users\\\\strider\\\\My Music\\\\iTunes\\\\iTunes Music\\\\Podcasts\\\\"],
                         'dword:00000001')

        key.parse('"A"=val')
        self.assertEqual(key.subkeys["A"], 'val')

        key.parse('"String with \"quotes\""=val')
        self.assertEqual(key.subkeys['String with \"quotes\"'], 'val')

        key.parse('"\"C:\\Program Files\\Windows Media Player\\wmplayer.exe\""="Yes"')
        self.assertEqual(key.subkeys['\"C:\\Program Files\\Windows Media Player\\wmplayer.exe\"'], '"Yes"')
