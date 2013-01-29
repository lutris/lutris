#!/usr/bin/python
import unittest
import os

from lutris.settings import PGA_DB
from lutris import pga


class TestPersonnalGameArchive(unittest.TestCase):
    def test_database(self):
        pga_path = os.path.join(os.path.expanduser('~'),
                                ".local/share/lutris/pga.db")
        self.assertEqual(PGA_DB, pga_path)
        self.assertTrue(os.path.exists(PGA_DB))

    def test_add_game(self):
        pga.add_game(name="LutrisTest", machine="Linux", runner="Linux")
        game_list = pga.get_games()
        print(game_list)
        #self.assertTrue("LutrisTest" in game_list)

    def test_delete_game(self):
        pga.delete_game("LutrisTest")

if __name__ == '__main__':
    unittest.main()
