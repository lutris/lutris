import os
from lutris import pga
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig
from mmap import mmap
from lutris.util.scanfolder import scan_folder
from lxml import etree

NAME = "dolphin"
INSTALLER_SLUG = "dolphin"
TDB_DB_CACHE = None

def add_or_update(rom,config):
    logger.info("updating or adding %s."%str(rom["name"]))

    config_id = make_game_config_id(rom["slug"])
    rom["configpath"] = config_id

    pga.add_or_update(**rom)

    gameConfig = LutrisConfig(
        runner_slug = "dolphin",
        game_config_id=config_id
    )
    gameConfig.raw_game_config.update(config)
    gameConfig.save()


def rom_read_data(location):
    def scan_to_00(mm,start):
        buff = b""
        achar = None
        number = start
        while achar != 0:
            achar = mm[number]
            if achar != 0:
                buff += bytes((achar,))
            number += 1
        return buff

    def bytes_to_str(b):
        return str(b)[2:-1]

    romType = None

    romType = get_rom_type(location)
    assert type(romType) == str

    rom = open(location,"r+b")
    mm = mmap(rom.fileno(), 0)
    data = {"installer_slug":INSTALLER_SLUG,
        "runner":"dolphin"}
    config = {}

    if romType == "wbfs file":
        assert mm[0:4] == b"WBFS"
        data["name"] = bytes_to_str(scan_to_00(mm,0x220))
        data["slug"] = bytes_to_str(scan_to_00(mm,0x200))
        data["installed"] = 1
        config["main_file"] = location
    else:
        raise

    return data, config


def get_rom_type(location):
    if location.split(".")[-1] in ["wbfs"]:
        return "wbfs file"
    return False


def sync_with_lutris():
    roms_games = {
        game['slug']: game
        for game in pga.get_games_where(installer_slug=INSTALLER_SLUG,
                                        installed=1)
    }
    
    runner_config = LutrisConfig(runner_slug="dolphin")
    scanDir = []
    scanDir = [runner_config.raw_config["dolphin"]["rom_directory"]]
    roms = []
    for element in scan_folder(scanDir):
        if get_rom_type(element) != False:
            try:
                roms.append(rom_read_data(element))
            except:
                logger.error("failed to add the dolphin rom at %s." % element)

    for romDouble in roms:
        rom, config = romDouble
        add_or_update(rom,config)
