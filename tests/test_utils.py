import os
from collections import OrderedDict
from unittest import TestCase
from lutris.util import system
from lutris.util.steam import vdf
from lutris.util import strings
from lutris.util import fileio


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
        vdf_data = vdf.to_vdf(dict_data)
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

    def test_get_formatted_playtime(self):
        self.assertEqual(strings.get_formatted_playtime(None), "No play time recorded")
        self.assertEqual(strings.get_formatted_playtime(1.0), "1 hour")
        self.assertEqual(strings.get_formatted_playtime(2.0), "2 hours")
        self.assertEqual(strings.get_formatted_playtime(0.5), "30 minutes")
        self.assertEqual(strings.get_formatted_playtime(1.5), "1 hour and 30 minutes")
        self.assertEqual(strings.get_formatted_playtime(45.90), "45 hours and 53 minutes")

class TestVersionSort(TestCase):
    def test_parse_version(self):
        self.assertEqual(strings.parse_version("3.6-staging"), ([3, 6], '', '-staging'))

    def test_versions_are_correctly_sorted(self):
        versions = ['1.8', '1.7.4', '1.9.1', '1.9.10', '1.9.4']
        versions = strings.version_sort(versions)
        self.assertEqual(versions[0], '1.7.4')
        self.assertEqual(versions[1], '1.8')
        self.assertEqual(versions[2], '1.9.1')
        self.assertEqual(versions[3], '1.9.4')
        self.assertEqual(versions[4], '1.9.10')

    def test_version_sorting_supports_extra_strings(self):
        versions = [
            '1.8', '1.8-staging',
            '1.7.4', '1.9.1',
            '1.9.10-staging', '1.9.10',
            '1.9.4', 'staging-1.9.4'
        ]
        versions = strings.version_sort(versions)
        self.assertEqual(versions[0], '1.7.4')
        self.assertEqual(versions[1], '1.8')
        self.assertEqual(versions[2], '1.8-staging')
        self.assertEqual(versions[3], '1.9.1')
        self.assertEqual(versions[4], '1.9.4')
        self.assertEqual(versions[5], 'staging-1.9.4')
        self.assertEqual(versions[6], '1.9.10')
        self.assertEqual(versions[7], '1.9.10-staging')

    def test_versions_can_be_reversed(self):
        versions = ['1.9', '1.6', '1.7', '1.8']
        versions = strings.version_sort(versions, reverse=True)
        self.assertEqual(versions[0], '1.9')
        self.assertEqual(versions[3], '1.6')


class TestEvilConfigParser(TestCase):
    def setUp(self):
        self.config_path = os.path.join(os.path.dirname(__file__), 'test.ini')

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_config_parse_can_write_to_disk(self):
        parser = fileio.EvilConfigParser(dict_type=fileio.MultiOrderedDict)
        parser.add_section('Test')
        parser.set('Test', 'key', 'value')
        with open(self.config_path, 'wb') as config:
            parser.write(config)


class TestUnpackDependencies(TestCase):
    def test_single_dependency(self):
        string = 'quake'
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(dependencies, ['quake'])

    def test_multiple_dependencies(self):
        string = 'quake,  quake-1,quake-steam, quake-gog   '
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(dependencies, ['quake', 'quake-1', 'quake-steam', 'quake-gog'])

    def test_dependency_options(self):
        string = 'quake,  quake-1,quake-steam | quake-gog|quake-humble   '
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(dependencies, ['quake', 'quake-1', ('quake-steam', 'quake-gog', 'quake-humble')])

    def test_strips_extra_commas(self):
        string = ', , , ,, ,,,,quake,  quake-1,quake-steam | quake-gog|quake-humble |||| , |, | ,|,| ,  '
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(dependencies, ['quake', 'quake-1', ('quake-steam', 'quake-gog', 'quake-humble')])


class TestSubstitute(TestCase):
    def test_can_sub_game_files_with_dashes_in_key(self):
        replacements = {'steam-data': '/tmp'}
        self.assertEqual(system.substitute('--path=$steam-data', replacements), '--path=/tmp')
