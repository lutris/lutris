#!/usr/bin/python
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lutris.config import LutrisConfig

from lutris.runners.steam import steam

steam = steam()

steam.get_appid_list()
print steam.game_list
