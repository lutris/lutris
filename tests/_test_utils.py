import os
from collections import OrderedDict
from unittest import TestCase

from lutris.util import fileio, strings, system
from lutris.util.steam import vdfutils
from lutris.util.wine import wine


class TestFileUtils(TestCase):
    def test_file_ids_are_correctly_transformed(self):
        file_id = "foo-bar"
        self.assertEqual(system.python_identifier(file_id), "foo-bar")

        file_id = "${foo-bar}"
        self.assertEqual(system.python_identifier(file_id), "${foo_bar}")

        file_id = "${foo-bar} ${a-b}"
        self.assertEqual(system.python_identifier(file_id), "${foo_bar} ${a_b}")

        file_id = "${foo-bar} a-b"
        self.assertEqual(system.python_identifier(file_id), "${foo_bar} a-b")

        file_id = "${foo-bar-bang}"
        self.assertEqual(system.python_identifier(file_id), "${foo_bar_bang}")

        file_id = "${foo-bar bang}"
        self.assertEqual(system.python_identifier(file_id), "${foo-bar bang}")

    def test_file_ids_are_substitued(self):
        fileid = "${foo-bar}"
        _files = {"foo-bar": "/foo/bar"}
        self.assertEqual(system.substitute(fileid, _files), "/foo/bar")


class TestSteamUtils(TestCase):
    def test_dict_to_vdf(self):
        appstate = OrderedDict()
        userconfig = OrderedDict()
        userconfig["gameid"] = "13240"
        userconfig["name"] = "Unreal Tournament"
        appstate["UserConfig"] = userconfig
        appstate["StateFlags"] = "4"
        appstate["appID"] = "13240"
        dict_data = OrderedDict()
        dict_data["AppState"] = appstate

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
        vdf_data = vdfutils.to_vdf(dict_data)
        self.assertEqual(vdf_data.strip(), expected_vdf.strip())


class TestStringUtils(TestCase):
    def test_slugify_with_nonwestern_name(self):
        name = "メイド☆ぱらだいす ～目指せ！メイドナンバーワン！～"
        slug = strings.slugify(name)
        self.assertTrue(len(slug) > 0)

    def test_gtk_safe_urls(self):
        self.assertEqual(strings.gtk_safe_urls("foo bar"), "foo bar")
        self.assertEqual(
            strings.gtk_safe_urls("foo http://lutris.net bar"),
            'foo <a href="http://lutris.net">http://lutris.net</a> bar',
        )
        self.assertEqual(
            strings.gtk_safe_urls("http://lutris.net"),
            '<a href="http://lutris.net">http://lutris.net</a>',
        )
        text = "foo http://lutris.net bar http://strycore.com"
        expected = (
            'foo <a href="http://lutris.net">http://lutris.net</a> '
            'bar <a href="http://strycore.com">http://strycore.com</a>'
        )
        self.assertEqual(strings.gtk_safe_urls(text), expected)

    def test_get_formatted_playtime(self):
        self.assertEqual(strings.get_formatted_playtime(None), strings.NO_PLAYTIME)
        self.assertEqual(strings.get_formatted_playtime(1.0), "1 hour")
        self.assertEqual(strings.get_formatted_playtime(2.0), "2 hours")
        self.assertEqual(strings.get_formatted_playtime("1.04"), "1 hour 2 minutes")
        self.assertEqual(strings.get_formatted_playtime("-"), strings.NO_PLAYTIME)
        self.assertEqual(strings.get_formatted_playtime(0.5), "30 minutes")
        self.assertEqual(strings.get_formatted_playtime(1.5), "1 hour 30 minutes")
        self.assertEqual(strings.get_formatted_playtime(45.90), "45 hours 54 minutes")

    def test_parse_playtime(self):
        self.assertEqual(strings.parse_playtime("0"), 0)
        self.assertEqual(strings.parse_playtime("2.5"), 2.5)
        self.assertEqual(strings.parse_playtime("30m"), 0.5)
        self.assertEqual(strings.parse_playtime("30 min"), 0.5)
        self.assertEqual(strings.parse_playtime("30 minutes"), 0.5)
        self.assertEqual(strings.parse_playtime("1 hour"), 1)
        self.assertEqual(strings.parse_playtime("1h"), 1)
        self.assertEqual(strings.parse_playtime("1 hour 30 minutes"), 1.5)
        self.assertEqual(strings.parse_playtime("1hour 30minutes"), 1.5)
        self.assertEqual(strings.parse_playtime("1hour30minutes"), 1.5)
        self.assertEqual(strings.parse_playtime("1hour30minute"), 1.5)
        self.assertEqual(strings.parse_playtime("1HoUr30MiNuTe"), 1.5)
        self.assertEqual(strings.parse_playtime("1h30min"), 1.5)
        self.assertEqual(strings.parse_playtime("1h30m"), 1.5)
        self.assertEqual(strings.parse_playtime("1H30M"), 1.5)
        self.assertEqual(strings.parse_playtime("1 h 30 m"), 1.5)
        self.assertEqual(strings.parse_playtime("2h45m"), 2.75)
        self.assertEqual(strings.parse_playtime("2h45"), 2.75)
        self.assertEqual(strings.parse_playtime("2:45"), 2.75)


class TestVersionSort(TestCase):
    def test_parse_version(self):
        self.assertEqual(
            wine.parse_wine_version("3.6-staging"), ([3, 6], "-staging", "")
        )

    def test_versions_are_correctly_sorted(self):
        versions = ["1.8", "1.7.4", "1.9.1", "1.9.10", "1.9.4"]
        versions = wine.version_sort(versions)
        self.assertEqual(versions[0], "1.7.4")
        self.assertEqual(versions[1], "1.8")
        self.assertEqual(versions[2], "1.9.1")
        self.assertEqual(versions[3], "1.9.4")
        self.assertEqual(versions[4], "1.9.10")

    def test_version_sorting_supports_extra_strings(self):
        versions = [
            "1.8",
            "1.8-staging",
            "1.7.4",
            "1.9.1",
            "1.9.10-staging",
            "1.9.10",
            "1.9.4",
            "staging-1.9.4",
        ]
        versions = wine.version_sort(versions)
        self.assertEqual(versions[0], "1.7.4")
        self.assertEqual(versions[1], "1.8")
        self.assertEqual(versions[2], "1.8-staging")
        self.assertEqual(versions[3], "1.9.1")
        self.assertEqual(versions[4], "1.9.4")
        self.assertEqual(versions[5], "staging-1.9.4")
        self.assertEqual(versions[6], "1.9.10")
        self.assertEqual(versions[7], "1.9.10-staging")

    def test_versions_can_be_reversed(self):
        versions = ["1.9", "1.6", "1.7", "1.8"]
        versions = wine.version_sort(versions, reverse=True)
        self.assertEqual(versions[0], "1.9")
        self.assertEqual(versions[3], "1.6")


class TestEvilConfigParser(TestCase):
    def setUp(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "test.ini")

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_config_parse_can_write_to_disk(self):
        parser = fileio.EvilConfigParser(dict_type=fileio.MultiOrderedDict)
        parser.add_section("Test")
        parser.set("Test", "key", "value")
        with open(self.config_path, "wb") as config:
            parser.write(config)


class TestUnpackDependencies(TestCase):
    def test_single_dependency(self):
        string = "quake"
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(dependencies, ["quake"])

    def test_multiple_dependencies(self):
        string = "quake,  quake-1,quake-steam, quake-gog   "
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(dependencies, ["quake", "quake-1", "quake-steam", "quake-gog"])

    def test_dependency_options(self):
        string = "quake,  quake-1,quake-steam | quake-gog|quake-humble   "
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(
            dependencies,
            ["quake", "quake-1", ("quake-steam", "quake-gog", "quake-humble")],
        )

    def test_strips_extra_commas(self):
        string = ", , , ,, ,,,,quake,  quake-1,quake-steam | quake-gog|quake-humble |||| , |, | ,|,| ,  "
        dependencies = strings.unpack_dependencies(string)
        self.assertEqual(
            dependencies,
            ["quake", "quake-1", ("quake-steam", "quake-gog", "quake-humble")],
        )


class TestSplitArguments(TestCase):
    """Tests for split_arguments — both POSIX (default) and Wine (keep_quotes) modes."""

    # --- default POSIX mode ---

    def test_simple_args_no_quotes(self):
        self.assertEqual(
            strings.split_arguments("--fullscreen --windowed"),
            ["--fullscreen", "--windowed"],
        )

    def test_empty_string(self):
        self.assertEqual(strings.split_arguments(""), [])

    def test_none_equivalent(self):
        self.assertEqual(strings.split_arguments(None), [])

    def test_posix_strips_double_quotes(self):
        # POSIX: quotes group and are stripped — correct for Linux-native programs
        self.assertEqual(
            strings.split_arguments('--config "/path/with spaces"'),
            ["--config", "/path/with spaces"],
        )

    def test_posix_strips_single_quotes(self):
        self.assertEqual(
            strings.split_arguments("--name 'my game'"), ["--name", "my game"]
        )

    # --- keep_quotes=True (Wine) mode ---

    def test_keep_quotes_simple_args_unchanged(self):
        # No quotes → same result in both modes
        self.assertEqual(
            strings.split_arguments("--fullscreen --windowed", keep_quotes=True),
            ["--fullscreen", "--windowed"],
        )

    def test_keep_quotes_preserves_double_quotes_on_value(self):
        # Windows-style: INI="path with spaces" must survive into the Wine command line
        result = strings.split_arguments(
            'INI="C:\\GOG Games\\game.ini"', keep_quotes=True
        )
        self.assertEqual(result, ['INI="C:\\GOG Games\\game.ini"'])

    def test_keep_quotes_groups_space_within_quotes(self):
        # The quoted section is one token despite containing spaces
        result = strings.split_arguments(
            '"C:\\My Games\\game.exe" --fullscreen', keep_quotes=True
        )
        self.assertEqual(result, ['"C:\\My Games\\game.exe"', "--fullscreen"])

    def test_keep_quotes_multiple_windows_args(self):
        # The original bug: multiple key="value with spaces" args were being merged or mangled
        args = 'INI="C:\\GOG Games\\TNM\\TNM.ini" USERINI="C:\\GOG Games\\TNM\\TNMUser.ini" log=TNM.log'
        result = strings.split_arguments(args, keep_quotes=True)
        self.assertEqual(
            result,
            [
                'INI="C:\\GOG Games\\TNM\\TNM.ini"',
                'USERINI="C:\\GOG Games\\TNM\\TNMUser.ini"',
                "log=TNM.log",
            ],
        )

    def test_keep_quotes_mixed_prefix_and_quoted_value(self):
        # Key=value where only the value is quoted — common Windows pattern
        result = strings.split_arguments(
            '--config="my settings.cfg" --verbose', keep_quotes=True
        )
        self.assertEqual(result, ['--config="my settings.cfg"', "--verbose"])

    def test_keep_quotes_single_quotes_preserved(self):
        result = strings.split_arguments("--name 'my game'", keep_quotes=True)
        self.assertEqual(result, ["--name", "'my game'"])


class TestSubstitute(TestCase):
    def test_can_sub_game_files_with_dashes_in_key(self):
        replacements = {"steam-data": "/tmp"}
        self.assertEqual(
            system.substitute("--path=$steam-data", replacements), "--path=/tmp"
        )
