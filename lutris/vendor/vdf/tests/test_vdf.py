import unittest
import mock
import sys

try:
        from StringIO import StringIO
except ImportError:
        from io import StringIO

import vdf


class testcase_helpers_escapes(unittest.TestCase):
    # https://github.com/ValveSoftware/source-sdk-2013/blob/0d8dceea4310fde5706b3ce1c70609d72a38efdf/sp/src/tier1/utlbuffer.cpp#L57-L68
    esc_chars_raw = "aa\n\t\v\b\r\f\a\\?\"'bb"
    esc_chars_escaped = 'aa\\n\\t\\v\\b\\r\\f\\a\\\\\\?\\"\\\'bb'

    def test_escape(self):
        self.assertEqual(vdf._escape(self.esc_chars_raw), self.esc_chars_escaped)

    def test_unescape(self):
        self.assertEqual(vdf._unescape(self.esc_chars_escaped), self.esc_chars_raw)

    def test_escape_unescape(self):
        self.assertEqual(vdf._unescape(vdf._escape(self.esc_chars_raw)), self.esc_chars_raw)


class testcase_helpers_load(unittest.TestCase):
    def setUp(self):
        self.f = StringIO()

    def tearDown(self):
        self.f.close()

    @mock.patch("vdf.parse")
    def test_routine_loads(self, mock_parse):
        vdf.loads("")

        (fp,), _ = mock_parse.call_args

        self.assertIsInstance(fp, StringIO)

    def test_routine_loads_assert(self):
        for t in [5, 5.5, 1.0j, None, [], (), {}, lambda: 0, sys.stdin, self.f]:
            self.assertRaises(TypeError, vdf.loads, t)

    @mock.patch("vdf.parse")
    def test_routine_load(self, mock_parse):
        vdf.load(sys.stdin)
        mock_parse.assert_called_with(sys.stdin)

        vdf.load(self.f)
        mock_parse.assert_called_with(self.f)

    @mock.patch("vdf.parse")
    def test_routines_mapper_passing(self, mock_parse):
        vdf.load(sys.stdin, mapper=dict)
        mock_parse.assert_called_with(sys.stdin, mapper=dict)

        vdf.loads("", mapper=dict)
        (fp,), kw = mock_parse.call_args
        self.assertIsInstance(fp, StringIO)
        self.assertIs(kw['mapper'], dict)

        class CustomDict(dict):
            pass

        vdf.load(sys.stdin, mapper=CustomDict)
        mock_parse.assert_called_with(sys.stdin, mapper=CustomDict)
        vdf.loads("", mapper=CustomDict)
        (fp,), kw = mock_parse.call_args
        self.assertIsInstance(fp, StringIO)
        self.assertIs(kw['mapper'], CustomDict)

    def test_routine_load_assert(self):
        for t in [5, 5.5, 1.0j, None, [], (), {}, lambda: 0, '']:
            self.assertRaises(TypeError, vdf.load, t)


class testcase_helpers_dump(unittest.TestCase):
    def setUp(self):
        self.f = StringIO()

    def tearDown(self):
        self.f.close()

    def test_routine_dumps_asserts(self):
        for x in [5, 5.5, 1.0j, True, None, (), {}, lambda: 0, sys.stdin, self.f]:
            for y in [5, 5.5, 1.0j, None, [], (), {}, lambda: 0, sys.stdin, self.f]:
                self.assertRaises(TypeError, vdf.dumps, x, y)

    def test_routine_dump_asserts(self):
        for x in [5, 5.5, 1.0j, True, None, (), {}, lambda: 0, sys.stdin, self.f]:
            for y in [5, 5.5, 1.0j, True, None, [], (), {}, lambda: 0]:
                self.assertRaises(TypeError, vdf.dump, x, y)

    def test_routine_dump_writing(self):
        class CustomDict(dict):
            pass

        for mapper in (dict, CustomDict):
            src = mapper({"asd": "123"})
            expected = vdf.dumps(src)

            vdf.dump(src, self.f)
            self.f.seek(0)

        self.assertEqual(expected, self.f.read())


class testcase_routine_parse(unittest.TestCase):
    def test_parse_bom_removal(self):
        result = vdf.loads(vdf.BOMS + '"asd" "123"')
        self.assertEqual(result, {'asd': '123'})

        if sys.version_info[0] is 2:
            result = vdf.loads(vdf.BOMS_UNICODE + '"asd" "123"')
            self.assertEqual(result, {'asd': '123'})

    def test_parse_source_asserts(self):
        for t in ['', 5, 5.5, 1.0j, True, None, (), {}, lambda: 0]:
            self.assertRaises(TypeError, vdf.parse, t)

    def test_parse_mapper_assert(self):
        self.assertRaises(TypeError, vdf.parse, StringIO(" "), mapper=list)

    def test_parse_file_source(self):
        self.assertEqual(vdf.parse(StringIO(" ")), {})

        class CustomDict(dict):
            pass

        self.assertEqual(vdf.parse(StringIO(" "), mapper=CustomDict), {})


class testcase_VDF(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(vdf.loads(""), {})

    def test_keyvalue_pairs(self):
        INPUT = '''
        "key1" "value1"
        key2 "value2"
        KEY3 "value3"
        "key4" value4
        "key5" VALUE5
        '''

        EXPECTED = {
            'key1': 'value1',
            'key2': 'value2',
            'KEY3': 'value3',
            'key4': 'value4',
            'key5': 'VALUE5',
        }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_keyvalue_open_quoted(self):
        INPUT = (
            '"key1" "a\n'
            'b\n'
            'c"\n'
            'key2 "a\n'
            'b\n'
            'c"\n'
            )

        EXPECTED = {
            'key1': 'a\nb\nc',
            'key2': 'a\nb\nc',
        }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_multi_keyvalue_pairs(self):
        INPUT = '''
        "root1"
        {
            "key1" "value1"
            key2 "value2"
            "key3" value3
        }
        root2
        {
            "key1" "value1"
            key2 "value2"
            "key3" value3
        }
        '''

        EXPECTED = {
            'root1': {
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3',
            },
            'root2': {
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3',
            }
        }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_deep_nesting(self):
        INPUT = '''
        "root"
        {
            node1
            {
                "node2"
                {
                    NODE3
                    {
                        "node4"
                        {
                            node5
                            {
                                "node6"
                                {
                                    NODE7
                                    {
                                        "node8"
                                        {
                                            "key" "value"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        '''

        EXPECTED = {
            'root': {
            'node1': {
            'node2': {
            'NODE3': {
            'node4': {
            'node5': {
            'node6': {
            'NODE7': {
            'node8': {
            'key': 'value'
            }}}}}}}}}
        }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_comments_and_blank_lines(self):
        INPUT = '''
        // this is comment
        "key1" "value1" // another comment
        key2 "value2"   // further comments
        "key3" value3   // useless comment

        key4 // comments comments comments
        {    // is this a comment?

        k v // comment

        }   // you only comment once

        // comment out of nowhere

        "key5" // pretty much anything here
        {      // is this a comment?

        K V    //comment

        }
        '''

        EXPECTED = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3',
            'key4': {
                'k': 'v'
            },
            'key5': {
                'K': 'V'
            },
        }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_hash_key(self):
        INPUT = '#include "asd.vdf"'
        EXPECTED = {'#include': 'asd.vdf'}

        self.assertEqual(vdf.loads(INPUT), EXPECTED)

        INPUT = '#base asd.vdf'
        EXPECTED = {'#base': 'asd.vdf'}

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_wierd_symbols_for_unquoted(self):
        INPUT = 'a asd.vdf\nb language_*lol*\nc zxc_-*.sss//'
        EXPECTED = {
            'a': 'asd.vdf',
            'b': 'language_*lol*',
            'c': 'zxc_-*.sss',
            }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)

    def test_merge_multiple_keys_on(self):
        INPUT = '''
        a
        {
            a 1
            b 2
        }
        a
        {
            a 3
            c 4
        }
        '''

        EXPECTED = {'a': {'a': '3', 'b': '2', 'c': '4'}}

        self.assertEqual(vdf.loads(INPUT, merge_duplicate_keys=True), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False, merge_duplicate_keys=True), EXPECTED)

    def test_merge_multiple_keys_off(self):
        INPUT = '''
        a
        {
            a 1
            b 2
        }
        a
        {
            a 3
            c 4
        }
        '''

        EXPECTED = {'a': {'a': '3', 'c': '4'}}

        self.assertEqual(vdf.loads(INPUT, merge_duplicate_keys=False), EXPECTED)
        self.assertEqual(vdf.loads(INPUT, escaped=False, merge_duplicate_keys=False), EXPECTED)

    def test_escape_before_last(self):
        INPUT = r'''
        "aaa\\" "1"
        "1" "bbb\\"
        '''

        EXPECTED = {
            "aaa\\": "1",
            "1": "bbb\\",
        }

        self.assertEqual(vdf.loads(INPUT), EXPECTED)

    def test_escape_before_last_unescaped(self):
        INPUT = r'''
        "aaa\\" "1"
        "1" "bbb\\"
        '''

        EXPECTED = {
            "aaa\\\\": "1",
            "1": "bbb\\\\",
        }

        self.assertEqual(vdf.loads(INPUT, escaped=False), EXPECTED)


class testcase_VDF_other(unittest.TestCase):
    def test_dumps_pretty_output(self):
        tests = [
            [
                {'1': '1'},
                '"1" "1"\n',
            ],
            [
                {'1': {'2': '2'}},
                '"1"\n{\n\t"2" "2"\n}\n',
            ],
            [
                {'1': {'2': {'3': '3'}}},
                '"1"\n{\n\t"2"\n\t{\n\t\t"3" "3"\n\t}\n}\n',
            ],
        ]
        for test, expected in tests:
            self.assertEqual(vdf.dumps(test, pretty=True), expected)

    def test_parse_exceptions(self):
        tests = [

            # expect bracket - invalid syntax
            '"asd"\n"zxc" "333"\n"',
            'asd\nzxc 333\n"',

            # invalid syntax
            '"asd" "123"\n"zxc" "333"\n"',
            'asd 123\nzxc 333\n"',
            '"asd\n\n\n\n\nzxc',
            '"asd" "bbb\n\n\n\n\nzxc',

            # one too many closing parenthasis
            '"asd"\n{\n"zxc" "123"\n}\n}\n}\n}\n',
            'asd\n{\nzxc 123\n}\n}\n}\n}\n',

            # unclosed parenthasis
            '"asd"\n{\n"zxc" "333"\n'
            'asd\n{\nzxc 333\n'
        ]

        for test in tests:
            self.assertRaises(SyntaxError, vdf.loads, test)
