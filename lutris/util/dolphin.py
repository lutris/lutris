from mmap import mmap


def scan_to_00(mm, start):
    """Read bytes from the mm mmap, beggining at the start
    offset and ending at the first 0x00.

    Return:
        bytes
    """
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
    data = {}
    with open(location, "r+") as rom:
        mm = mmap(rom.fileno(), 0)
        # the most of the scan of the game
        if mm[0:4] == b"WBFS":  # wii WBFS file
            data["name"] = bytes_to_str(scan_to_00(mm, 0x220))
            data["slug"] = "wii-" + bytes_to_str(scan_to_00(mm, 0x200))
        elif mm[0x18:0x1C] == b"\x5D\x1C\x9E\xA3":  # wii iso file
            data["name"] = bytes_to_str(scan_to_00(mm, 0x20))
            data["slug"] = "wii-" + bytes_to_str(scan_to_00(mm, 0x0))
        else:
            return False
    return data
