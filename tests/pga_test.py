#!/usr/bin/python

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lutris.config import LutrisConfig
from lutris.settings import PGA_PATH


class TestPersonnalGameArchive(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def __init__(self):
        pass

    def runTest(self):
        pga_path = os.path.join(os.path.expanduser('~'), ".local/share/pga.db")

        self.assertEqual(PGA_PATH, pga_path)

if __name__ == '__main__':
    test = TestPersonnalGameArchive()
    test.runTest()
