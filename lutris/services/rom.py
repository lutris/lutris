from mmap import mmap
import os
from lutris import pga
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig

NAME = "rom"
INSTALLER_SLUG = "rom"
TDB_DB_CACHE = None

def add_rom(rom, config):
    """ add a dolhin rom to the database ( update if game already exist )
    rom and config are list, respectively for the rom data and the runner config """
    logger.info("adding %s."%str(rom["name"]))

    config_id = make_game_config_id(rom["slug"])
    rom["configpath"] = config_id

    pga.add_or_update(**rom)

    game_config = LutrisConfig(
        runner_slug=rom["runner"],
        game_config_id=config_id
    )
    game_config.raw_game_config.update(config)
    game_config.save()


def scan_to_00(mm, start):
    """ read bytes from the mm mmap, beggining at the start offset and ending at the first 0x00.
    return a bytes object """
    buff = b""
    achar = None
    number = start
    while achar != 0:
        achar = mm[number]
        if achar != 0:
            buff += bytes((achar,))
        number += 1
    return buff

def bytes_to_str(byte):
    """ transform bytes to string with the default codec """
    return str(byte)[2:-1]

def rom_read_data(location):
    """ extract data from the rom location at location.
    return a dict with "data" and "config", to be applied to a game in Lutris """
    # TODO: extract the image of the rom

    data = {"installer_slug":INSTALLER_SLUG,
            "installed":1}
    config = {"main_file":location}

    with open(location, "r+") as rom:
        mm = mmap(rom.fileno(), 0)

        # the most of the scan of the game
        if mm[0:4] == b"WBFS": # wii WBFS file
            data["name"] = bytes_to_str(scan_to_00(mm, 0x220))
            data["slug"] = "wii-"+bytes_to_str(scan_to_00(mm, 0x200))
            data["runner"] = "dolphin"
            config['platform'] = 1
        elif mm[0x18:0x1C] == b"\x5D\x1C\x9E\xA3": # wii iso file
            data["name"] = bytes_to_str(scan_to_00(mm, 0x20))
            data["slug"] = "wii-"+bytes_to_str(scan_to_00(mm, 0x0))
            data["runner"] = "dolphin"
            config['platform'] = 1
        else:
            return False

    data["slug"] = slugify(data["slug"])
    return {"data":data, "config":config}



def sync_with_lutris():
    #roms_installed = {
    #    game['slug']: game
    #    for game in pga.get_games_where(installer_slug=INSTALLER_SLUG,
    #                                    installed=1)
    #}

    system_config = LutrisConfig()
    scan_directory = system_config.system_config["rom_directory"]
    roms = []
    roms_slug = []

    for folder, subfolder, files in os.walk(scan_directory,followlinks=True):
        for scanned_file in files:
            element = folder + "/" + scanned_file
            result = False
            try:
                result = rom_read_data(element)
            except:
                logger.error("failed to add the rom at %s." % element)
            if result != False:
                roms.append(result)
                roms_slug.append(result["data"]["slug"])


    for rom_data in roms:
        rom, config = rom_data["data"], rom_data["config"]
        if not rom in roms_slug:
            add_rom(rom, config)
