#!/usr/bin/python

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lutris.runners.steam import steam

class TestSomeStuff(unittest.TestCase):
    def __init__(self):
        self.steam_runner = steam()
    
    def runTest(self):
        # Assume that steam is not installed
        self.assertFalse(self.steam_runner.is_installed())
        # Assume wine is installed
        self.assertTrue(self.steam_runner.check_depends())
        
if __name__ == '__main__':
    test = TestSomeStuff()
    test.runTest() 