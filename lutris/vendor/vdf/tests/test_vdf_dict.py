import unittest
from vdf import VDFDict


class VDFDictCase(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(ValueError):
            VDFDict("asd zxc")
        with self.assertRaises(ValueError):
            VDFDict(5)
        with self.assertRaises(ValueError):
            VDFDict((('1',1), ('2', 2)))

    def test_repr(self):
        self.assertIsInstance(repr(VDFDict()), str)

    def test_len(self):
        self.assertEqual(len(VDFDict()), 0)
        self.assertEqual(len(VDFDict({'1':1})), 1)

    def test_verify_key_tuple(self):
        a = VDFDict()
        with self.assertRaises(ValueError):
            a._verify_key_tuple([])
        with self.assertRaises(ValueError):
            a._verify_key_tuple((1,))
        with self.assertRaises(ValueError):
            a._verify_key_tuple((1,1,1))
        with self.assertRaises(TypeError):
            a._verify_key_tuple((None, 'asd'))
        with self.assertRaises(TypeError):
            a._verify_key_tuple(('1', 'asd'))
        with self.assertRaises(TypeError):
            a._verify_key_tuple((1, 1))
        with self.assertRaises(TypeError):
            a._verify_key_tuple((1, None))

    def test_normalize_key(self):
        a = VDFDict()
        self.assertEqual(a._normalize_key('AAA'), (0, 'AAA'))
        self.assertEqual(a._normalize_key((5, 'BBB')), (5, 'BBB'))

    def test_normalize_key_exception(self):
        a = VDFDict()
        with self.assertRaises(TypeError):
            a._normalize_key(5)
        with self.assertRaises(TypeError):
            a._normalize_key([])
        with self.assertRaises(TypeError):
            a._normalize_key(None)

    def test_setitem(self):
        a = list(zip(map(str, range(5, 0, -1)), range(50, 0, -10)))
        b = VDFDict()
        for k,v in a:
            b[k] = v
        self.assertEqual(a, list(b.items()))

    def test_setitem_with_duplicates(self):
        a = list(zip(['5']*5, range(50, 0, -10)))
        b = VDFDict()
        for k,v in a:
            b[k] = v
        self.assertEqual(a, list(b.items()))

    def test_setitem_key_exceptions(self):
        with self.assertRaises(TypeError):
            VDFDict()[5] = None
        with self.assertRaises(TypeError):
            VDFDict()[(0, 5)] = None
        with self.assertRaises(ValueError):
            VDFDict()[(0, '5', 1)] = None

    def test_setitem_key_valid_types(self):
        VDFDict()['5'] = None
        VDFDict({'5': None})[(0, '5')] = None

    def test_setitem_keyerror_fullkey(self):
        with self.assertRaises(KeyError):
            VDFDict([("1", None)])[(1, "1")] = None

    def test_getitem(self):
        a = VDFDict([('1',2), ('1',3)])
        self.assertEqual(a['1'], 2)
        self.assertEqual(a[(0, '1')], 2)
        self.assertEqual(a[(1, '1')], 3)

    def test_del(self):
        a = VDFDict([("1",1),("1",2),("5",51),("1",3),("5",52)])
        b = [("1",1),("1",2),("1",3),("5",52)]
        del a["5"]
        self.assertEqual(list(a.items()), b)

    def test_del_by_fullkey(self):
        a = VDFDict([("1",1),("1",2),("5",51),("1",3),("5",52)])
        b = [("1",1),("1",2),("1",3),("5",52)]
        del a[(0, "5")]
        self.assertEqual(list(a.items()), b)

    def test_del_first_duplicate(self):
        a = [("1",1),("1",2),("1",3),("1",4)]
        b = VDFDict(a)

        del b["1"]
        del b["1"]
        del b[(0, "1")]
        del b[(0, "1")]

        self.assertEqual(len(b), 0)

    def test_del_exception(self):
        with self.assertRaises(KeyError):
            a = VDFDict()
            del a["1"]
        with self.assertRaises(KeyError):
            a = VDFDict({'1':1})
            del a[(1, "1")]

    def test_iter(self):
        a = VDFDict({"1": 1})
        iter(a).__iter__
        self.assertEqual(len(list(iter(a))), 1)

    def test_in(self):
        a = VDFDict({"1":2, "3":4, "5":6})
        self.assertTrue('1' in a)
        self.assertTrue((0, '1') in a)
        self.assertFalse('6' in a)
        self.assertFalse((1, '1') in a)

    def test_eq(self):
        self.assertEqual(VDFDict(), VDFDict())
        self.assertNotEqual(VDFDict(), VDFDict({'1':1}))
        self.assertNotEqual(VDFDict(), {'1':1})
        a = [("a", 1), ("b", 5), ("a", 11)]
        self.assertEqual(VDFDict(a), VDFDict(a))
        self.assertNotEqual(VDFDict(a), VDFDict(a[1:]))

    def test_clear(self):
        a = VDFDict([("1",2),("1",2),("5",3),("1",2)])
        a.clear()
        self.assertEqual(len(a), 0)
        self.assertEqual(len(a.keys()), 0)
        self.assertEqual(len(list(a.iterkeys())), 0)
        self.assertEqual(len(a.values()), 0)
        self.assertEqual(len(list(a.itervalues())), 0)
        self.assertEqual(len(a.items()), 0)
        self.assertEqual(len(list(a.iteritems())), 0)

    def test_get(self):
        a = VDFDict([('1',11), ('1',22)])
        self.assertEqual(a.get('1'), 11)
        self.assertEqual(a.get((1, '1')), 22)
        self.assertEqual(a.get('2', 33), 33)
        self.assertEqual(a.get((0, '2'), 44), 44)

    def test_setdefault(self):
        a = VDFDict([('1',11), ('1',22)])
        self.assertEqual(a.setdefault('1'), 11)
        self.assertEqual(a.setdefault((0, '1')), 11)
        self.assertEqual(a.setdefault('2'), None)
        self.assertEqual(a.setdefault((0, '2')), None)
        self.assertEqual(a.setdefault('3', 33), 33)

    def test_pop(self):
        a = VDFDict([('1',11),('2',22),('1',33),('2',44),('2',55)])
        self.assertEqual(a.pop('1'), 11)
        self.assertEqual(a.pop('1'), 33)
        with self.assertRaises(KeyError):
            a.pop('1')
        self.assertEqual(a.pop((1, '2')), 44)
        self.assertEqual(a.pop((1, '2')), 55)

    def test_popitem(self):
        a = [('1',11),('2',22),('1',33)]
        b = VDFDict(a)
        self.assertEqual(b.popitem(), a.pop())
        self.assertEqual(b.popitem(), a.pop())
        self.assertEqual(b.popitem(), a.pop())
        with self.assertRaises(KeyError):
            b.popitem()

    def test_update(self):
        a = VDFDict([("1",2),("1",2),("5",3),("1",2)])
        b = VDFDict()
        b.update([("1",2),("1",2)])
        b.update([("5",3),("1",2)])
        self.assertEqual(list(a.items()), list(b.items()))

    def test_update_exceptions(self):
        a = VDFDict()
        with self.assertRaises(TypeError):
            a.update(None)
        with self.assertRaises(TypeError):
            a.update(1)
        with self.assertRaises(TypeError):
            a.update("asd zxc")
        with self.assertRaises(ValueError):
            a.update([(1,1,1), (2,2,2)])

    map_test = [
            ("1", 2),
            ("4", 3),("4", 3),("4", 2),
            ("7", 2),
            ("1", 2),
        ]

    def test_keys(self):
        _dict = VDFDict(self.map_test)
        self.assertSequenceEqual(
            list(_dict.keys()),
            list(x[0] for x in self.map_test))

    def test_values(self):
        _dict = VDFDict(self.map_test)
        self.assertSequenceEqual(
            list(_dict.values()),
            list(x[1] for x in self.map_test))

    def test_items(self):
        _dict = VDFDict(self.map_test)
        self.assertSequenceEqual(
            list(_dict.items()),
            self.map_test)

    def test_direct_access_get(self):
        b = dict()
        a = VDFDict({"1":2, "3":4, "5":6})
        for k,v in a.items():
            b[k] = v
        self.assertEqual(dict(a.items()), b)

    def test_duplicate_keys(self):
        items = [('key1', 1), ('key1', 2), ('key3', 3), ('key1', 1)]
        keys = [x[0] for x in items]
        values = [x[1] for x in items]
        _dict = VDFDict(items)
        self.assertEqual(list(_dict.items()), items)
        self.assertEqual(list(_dict.keys()), keys)
        self.assertEqual(list(_dict.values()), values)

    def test_same_type_init(self):
        self.assertSequenceEqual(
            tuple(VDFDict(self.map_test).items()),
            tuple(VDFDict(VDFDict(self.map_test)).items()))

    def test_get_all_for(self):
        a = VDFDict([("1",2),("1",2**31),("5",3),("1",2)])
        self.assertEqual(
            list(a.get_all_for("1")),
            [2,2**31,2],
            )

    def test_get_all_for_invalid_key(self):
        a = VDFDict()
        with self.assertRaises(TypeError):
            a.get_all_for(None)
        with self.assertRaises(TypeError):
            a.get_all_for(5)
        with self.assertRaises(TypeError):
            a.get_all_for((0, '5'))

    def test_remove_all_for(self):
        a = VDFDict([("1",2),("1",2),("5",3),("1",2)])
        a.remove_all_for("1")
        self.assertEqual(list(a.items()), [("5",3)])
        self.assertEqual(len(a), 1)

    def test_remove_all_for_invalid_key(self):
        a = VDFDict()
        with self.assertRaises(TypeError):
            a.remove_all_for(None)
        with self.assertRaises(TypeError):
            a.remove_all_for(5)
        with self.assertRaises(TypeError):
            a.remove_all_for((0, '5'))

    def test_has_duplicates(self):
        # single level duplicate
        a = [('1', 11), ('1', 22)]
        b = VDFDict(a)
        self.assertTrue(b.has_duplicates())

        # duplicate in nested
        c = VDFDict({'1': b})
        self.assertTrue(c.has_duplicates())

        # duplicate in nested dict
        d = VDFDict({'1': {'2': {'3': b}}})
        self.assertTrue(d.has_duplicates())

        # duplicate in nested dict
        d = VDFDict({'1': {'2': {'3': None}}})
        self.assertFalse(d.has_duplicates())
