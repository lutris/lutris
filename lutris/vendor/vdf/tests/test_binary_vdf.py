import sys
import unittest

import vdf
from collections import OrderedDict

u = str if sys.version_info >= (3,) else unicode


class BinaryVDF(unittest.TestCase):
    def test_BASE_INT(self):
        repr(vdf.BASE_INT())

    def test_simple(self):
        pairs = [
            ('a', 'test'),
            ('a2', b'\xd0\xb0\xd0\xb1\xd0\xb2\xd0\xb3'.decode('utf-8')),
            ('bb', 1),
            ('bb2', -500),
            ('ccc', 1.0),
            ('dddd', vdf.POINTER(1234)),
            ('fffff', vdf.COLOR(1234)),
            ('gggggg', vdf.UINT_64(1234)),
            ('hhhhhhh', vdf.INT_64(-1234)),
        ]

        data = OrderedDict(pairs)
        data['level1-1'] = OrderedDict(pairs)
        data['level1-1']['level2-1'] = OrderedDict(pairs)
        data['level1-1']['level2-2'] = OrderedDict(pairs)
        data['level1-2'] = OrderedDict(pairs)

        result = vdf.binary_loads(vdf.binary_dumps(data), mapper=OrderedDict)

        self.assertEqual(data, result)

        result = vdf.binary_loads(vdf.binary_dumps(data, alt_format=True), mapper=OrderedDict, alt_format=True)

        self.assertEqual(data, result)

        result = vdf.vbkv_loads(vdf.vbkv_dumps(data), mapper=OrderedDict)

        self.assertEqual(data, result)

    def test_vbkv_empty(self):
        with self.assertRaises(ValueError):
            vdf.vbkv_loads(b'')

    def test_loads_empty(self):
        self.assertEqual(vdf.binary_loads(b''), {})

    def test_dumps_empty(self):
        self.assertEqual(vdf.binary_dumps({}), b'')

    def test_dumps_unicode(self):
        self.assertEqual(vdf.binary_dumps({u('a'): u('b')}), b'\x01a\x00b\x00\x08')

    def test_dumps_unicode_alternative(self):
        self.assertEqual(vdf.binary_dumps({u('a'): u('b')}, alt_format=True), b'\x01a\x00b\x00\x0b')

    def test_dumps_key_invalid_type(self):
        with self.assertRaises(TypeError):
            vdf.binary_dumps({1:1})
        with self.assertRaises(TypeError):
            vdf.binary_dumps({None:1})

    def test_dumps_value_invalid_type(self):
        with self.assertRaises(TypeError):
            vdf.binary_dumps({'': None})

    def test_alternative_format(self):
        with self.assertRaises(SyntaxError):
            vdf.binary_loads(b'\x00a\x00\x00b\x00\x0b\x0b')
        with self.assertRaises(SyntaxError):
            vdf.binary_loads(b'\x00a\x00\x00b\x00\x08\x08', alt_format=True)

    def test_loads_unbalanced_nesting(self):
        with self.assertRaises(SyntaxError):
            vdf.binary_loads(b'\x00a\x00\x00b\x00\x08')
        with self.assertRaises(SyntaxError):
            vdf.binary_loads(b'\x00a\x00\x00b\x00\x08\x08\x08\x08')

    def test_loads_unknown_type(self):
        with self.assertRaises(SyntaxError):
            vdf.binary_loads(b'\x33a\x00\x08')

    def test_loads_unterminated_string(self):
        with self.assertRaises(SyntaxError):
            vdf.binary_loads(b'\x01abbbb')

    def test_loads_type_checks(self):
        with self.assertRaises(TypeError):
            vdf.binary_loads(None)
        with self.assertRaises(TypeError):
            vdf.binary_loads(b'', mapper=list)

    def test_merge_multiple_keys_on(self):
        # VDFDict([('a', VDFDict([('a', '1'), ('b', '2')])), ('a', VDFDict([('a', '3'), ('c', '4')]))])
        test = b'\x00a\x00\x01a\x001\x00\x01b\x002\x00\x08\x00a\x00\x01a\x003\x00\x01c\x004\x00\x08\x08'
        result = {'a': {'a': '3', 'b': '2', 'c': '4'}}

        self.assertEqual(vdf.binary_loads(test, merge_duplicate_keys=True), result)

    def test_merge_multiple_keys_off(self):
        # VDFDict([('a', VDFDict([('a', '1'), ('b', '2')])), ('a', VDFDict([('a', '3'), ('c', '4')]))])
        test = b'\x00a\x00\x01a\x001\x00\x01b\x002\x00\x08\x00a\x00\x01a\x003\x00\x01c\x004\x00\x08\x08'
        result = {'a': {'a': '3', 'c': '4'}}

        self.assertEqual(vdf.binary_loads(test, merge_duplicate_keys=False), result)

    def test_vbkv_loads_empty(self):
        with self.assertRaises(ValueError):
            vdf.vbkv_loads(b'')

    def test_vbkv_dumps_empty(self):
        self.assertEqual(vdf.vbkv_dumps({}), b'VBKV\x00\x00\x00\x00')

    def test_vbkv_loads_invalid_header(self):
        with self.assertRaises(ValueError):
            vdf.vbkv_loads(b'DD1235764tdffhghsdf')

    def test_vbkv_loads_invalid_checksum(self):
        with self.assertRaises(ValueError):
            vdf.vbkv_loads(b'VBKV\x01\x02\x03\x04\x00a\x00\x0b\x0b')

    def test_loads_utf8_invalmid(self):
        self.assertEqual({'aaa': b'bb\xef\xbf\xbdbb'.decode('utf-8')}, vdf.binary_loads(b'\x01aaa\x00bb\xffbb\x00\x08'))

    def test_loads_utf16(self):
        self.assertEqual({'aaa': b'b\x00b\x00\xff\xffb\x00b\x00'.decode('utf-16le')}, vdf.binary_loads(b'\x05aaa\x00b\x00b\x00\xff\xffb\x00b\x00\x00\x00\x08'))
