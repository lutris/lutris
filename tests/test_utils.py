from unittest import TestCase
from lutris.util import files


class TestFileUtils(TestCase):
    def test_file_ids_are_correctly_transformed(self):
        file_id = 'foo-bar'
        self.assertEqual(files.python_identifier(file_id), 'foo-bar')

        file_id = '${foo-bar}'
        self.assertEqual(files.python_identifier(file_id), '${foo_bar}')

        file_id = '${foo-bar} ${a-b}'
        self.assertEqual(files.python_identifier(file_id), '${foo_bar} ${a_b}')

        file_id = '${foo-bar} a-b'
        self.assertEqual(files.python_identifier(file_id), '${foo_bar} a-b')

        file_id = '${foo-bar-bang}'
        self.assertEqual(files.python_identifier(file_id), '${foo_bar_bang}')

        file_id = '${foo-bar bang}'
        self.assertEqual(files.python_identifier(file_id), '${foo-bar bang}')

    def test_file_ids_are_substitued(self):
        fileid = '${foo-bar}'
        _files = {
            'foo-bar': "/foo/bar"
        }
        self.assertEqual(files.substitute(fileid, _files), "/foo/bar")
