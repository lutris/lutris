#!/usr/bin/python
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lutris.config import LutrisConfig

class PathTest(unittest.TestCase):
    def __init__(self):
       self.config = LutrisConfig(runner='wine') 

    def runTest(self):
        print self.config.get_path()
        self.assertEqual(self.config.get_path(), '/home/mathieu')

if __name__ == '__main__':
    pathtest = PathTest()
    pathtest.runTest()
