"""Handle EGS configuration"""
import os
from collections import OrderedDict, defaultdict

from lutris.util import system
from lutris.util.log import logger
from lutris.runners import wineegs


def get_egs_data_path():
    runner = wineegs.wineegs()
    return runner.egs_data_path

def get_egs_prefix_path():    
    runner = wineegs.wineegs()
    return runner.prefix_path
