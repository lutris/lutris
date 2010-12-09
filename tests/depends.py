#!/usr/bin/python
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
# 
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
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
