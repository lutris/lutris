#!/usr/bin/python

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSomeStuff(unittest.TestCase):
    def __init__(self):
        """Do some stuff"""
        pass
    
    def runTest(self):
        self.assertEqual(True, True)
        
if __name__ == '__main__':
    test = TestSomeStuff()
    test.runTest()