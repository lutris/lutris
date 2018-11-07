from mmap import mmap
from lutris import pga
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig
from lutris.util.scanfolder import scan_folder

NAME = "dolphin"
INSTALLER_SLUG = "dolphin"
TDB_DB_CACHE = None

def add_dolphin_rom(rom, config):
    """ add a dolhin rom to the database ( update if game already exist )
    rom and config are list, respectively for the rom data and the runner config """
    logger.info("adding %s."%str(rom["name"]))

    config_id = make_game_config_id(rom["slug"])
    rom["configpath"] = config_id

    pga.add_or_update(**rom)

    game_config = LutrisConfig(
        runner_slug="dolphin",
        game_config_id=config_id
    )
    game_config.raw_game_config.update(config)
    game_config.save()


def rom_read_data(location):
    """ extract data from the dolphin rom location at location.
    return the tuple of data and of config, to be applied to a game in Lutris """
    # TODO: extract the image of the rom
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

    rom_type = None

    rom_type = get_rom_type(location)
    assert isinstance(rom_type, str)

    rom = open(location, "r+b")
    mm = mmap(rom.fileno(), 0)
    data = {"installer_slug":INSTALLER_SLUG,
            "runner":"dolphin",
            "installed":1,}
    config = {"main_file":location}

    if rom_type == "wbfs file":
        assert mm[0:4] == b"WBFS"
        data["name"] = bytes_to_str(scan_to_00(mm, 0x220))
        data["slug"] = bytes_to_str(scan_to_00(mm, 0x200))
        config['platform'] = 1
    elif rom_type == "iso file":
        assert mm[0x18:0x1C] == b"\x5D\x1C\x9E\xA3"
        data["name"] = bytes_to_str(scan_to_00(mm, 0x20))
        data["slug"] = bytes_to_str(scan_to_00(mm, 0x0))
        config['platform'] = 1

    data["slug"] = slugify(data["slug"])


    return data, config


def get_rom_type(location):
    """return the type of rom at location based on the file extansion, False if nothing is found"""
    extension = location.split(".")[-1]
    if extension in ["wbfs"]:
        return "wbfs file"
    elif extension in ["iso"]:
        return "iso file"
    return False


def sync_with_lutris():
    #dolphin_games = {
    #    game['slug']: game
    #    for game in pga.get_games_where(installer_slug=INSTALLER_SLUG,
    #                                    installed=1)
    #}

    runner_config = LutrisConfig(runner_slug="dolphin")
    scan_directory = [runner_config.raw_config["dolphin"]["rom_directory"]]
    roms = []
    roms_slug = []
    for element in scan_folder(scan_directory):
        if get_rom_type(element) != False:
            try:
                rom, config = rom_read_data(element)
                roms.append((rom, config))
                roms_slug.append(rom["slug"])
            except:
                logger.error("failed to add the dolphin rom at %s." % element)

    for rom_double in roms:
        rom, config = rom_double
        if not rom in roms_slug:
            add_dolphin_rom(rom, config)
