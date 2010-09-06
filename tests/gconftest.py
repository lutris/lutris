import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lutris.gconfwrapper import GconfWrapper


class TestGConfWrapper(unittest.TestCase):
    def __init__(self):
        self.gconf = GconfWrapper()

    def runTest(self):
        self.assertEqual(self.gconf.has_key('/apps/metacity/general/button_layout'), True)
        self.assertEqual(self.gconf.has_key('/apps/metacity/general/bouton_disposition'), False)
        self.assertEqual(self.gconf.has_key('/foo/bar'), False)

        self.assertEqual(self.gconf.get_key('/foo/bar'), None)
        self.assertEqual(self.gconf.get_key('/apps/metacity/general/raise_on_click'), True)
        self.assertTrue(self.gconf.set_key('/apps/metacity/general/auto_raise_delay', 500, override_type = True))
        self.assertEqual(self.gconf.get_key('/apps/metacity/general/auto_raise_delay'), 500)

        self.assertTrue(self.gconf.set_key('/apps/metacity/general/raise_on_click', False))
        self.assertEqual(self.gconf.get_key('/apps/metacity/general/raise_on_click'), False)
        self.assertTrue(self.gconf.set_key('/apps/metacity/general/raise_on_click', True))
        self.assertEqual(self.gconf.get_key('/apps/metacity/general/raise_on_click'), True)

        self.assertTrue(self.gconf.set_key('/apps/metacity/general/auto_raise_delay', 499))
        self.assertEqual(self.gconf.get_key('/apps/metacity/general/auto_raise_delay'), 499)
        self.assertFalse(self.gconf.set_key('/apps/metacity/general/auto_raise_delay', "Five hundred"))
        self.assertTrue(self.gconf.set_key('/apps/metacity/general/auto_raise_delay', 500))

        print 'testing new keys'
        self.assertTrue(self.gconf.set_key('/apps/lutris/tests/foo', "dressed like pazuzu", override_type = True))
        self.assertEqual(self.gconf.get_key('/apps/lutris/tests/foo'), "dressed like pazuzu")
        self.assertEqual(self.gconf.all_dirs('/apps/lutris'), ['tests'])

if __name__ == '__main__':
    test = TestGConfWrapper()
    test.runTest()

