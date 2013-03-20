#!/usr/bin/python
import unittest
import os
from lutris import pga

TEST_PGA_PATH = os.path.join(os.path.dirname(__file__), 'fixtures/pga.db')


class TestPersonnalGameArchive(unittest.TestCase):
    def setUp(self):
        pga.PGA_DB = TEST_PGA_PATH
        pga.create()

    def tearDown(self):
        os.remove(TEST_PGA_PATH)

    def test_add_game(self):
        pga.add_game(name="LutrisTest", machine="Linux", runner="Linux")
        game_list = pga.get_games()
        game_names = [item[1] for item in game_list]
        self.assertTrue("LutrisTest" in game_names)

    def test_delete_game(self):
        pga.delete_game("LutrisTest")

if __name__ == '__main__':
    unittest.main()
