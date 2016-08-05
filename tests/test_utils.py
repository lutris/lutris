from collections import OrderedDict
from unittest import TestCase
from lutris.util import system
from lutris.util import steam
from lutris.util import strings


class TestFileUtils(TestCase):
    def test_file_ids_are_correctly_transformed(self):
        file_id = 'foo-bar'
        self.assertEqual(system.python_identifier(file_id), 'foo-bar')

        file_id = '${foo-bar}'
        self.assertEqual(system.python_identifier(file_id), '${foo_bar}')

        file_id = '${foo-bar} ${a-b}'
        self.assertEqual(system.python_identifier(file_id), '${foo_bar} ${a_b}')

        file_id = '${foo-bar} a-b'
        self.assertEqual(system.python_identifier(file_id), '${foo_bar} a-b')

        file_id = '${foo-bar-bang}'
        self.assertEqual(system.python_identifier(file_id), '${foo_bar_bang}')

        file_id = '${foo-bar bang}'
        self.assertEqual(system.python_identifier(file_id), '${foo-bar bang}')

    def test_file_ids_are_substitued(self):
        fileid = '${foo-bar}'
        _files = {
            'foo-bar': "/foo/bar"
        }
        self.assertEqual(system.substitute(fileid, _files), "/foo/bar")


class TestSteamUtils(TestCase):
    def test_dict_to_vdf(self):
        appstate = OrderedDict()
        userconfig = OrderedDict()
        userconfig['gameid'] = "13240"
        userconfig['name'] = "Unreal Tournament"
        appstate['UserConfig'] = userconfig
        appstate['StateFlags'] = '4'
        appstate['appID'] = '13240'
        dict_data = OrderedDict()
        dict_data['AppState'] = appstate

        expected_vdf = """"AppState"
{
\t"UserConfig"
\t{
\t\t"gameid"\t\t"13240"
\t\t"name"\t\t"Unreal Tournament"
\t}
\t"StateFlags"\t\t"4"
\t"appID"\t\t"13240"
}"""
        vdf_data = steam.to_vdf(dict_data)
        self.assertEqual(vdf_data.strip(), expected_vdf.strip())


class TestStringUtils(TestCase):
    def test_add_url_tags(self):
        self.assertEqual(strings.add_url_tags("foo bar"), "foo bar")
        self.assertEqual(
            strings.add_url_tags("foo http://lutris.net bar"),
            "foo <a href=\"http://lutris.net\">http://lutris.net</a> bar"
        )
        self.assertEqual(
            strings.add_url_tags("http://lutris.net"),
            "<a href=\"http://lutris.net\">http://lutris.net</a>"
        )
        text = "foo http://lutris.net bar http://strycore.com"
        expected = (
            'foo <a href="http://lutris.net">http://lutris.net</a> '
            'bar <a href="http://strycore.com">http://strycore.com</a>'
        )
        self.assertEqual(strings.add_url_tags(text), expected)
