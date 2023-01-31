import os

from lutris import settings
from lutris.util import http
from lutris.util.extract import extract_archive
from lutris.util.log import logger
from lutris.util.system import get_md5_hash

archive_formats = [".zip", ".7z", ".rar", ".gz"]
save_formats = [".srm"]
PLATFORM_PATTERNS = {
    "3DO": "3do",
    "Amiga CD32": "amiga-cd32",
    "Amiga": "amiga",
    "Master System": "sms",
    "Genesis": "md",
    "Game Gear": "gg",
    "Sega CD": "segacd",
    "Saturn": "saturn",
    "Dreamcast": "dc",
    "PICO": "pico",
    "ColecoVision": "colecovision",
    "Atari 8bit": "atari800",
    "Atari - 8-bit": "atari800",
    "Atari 2600": "atari2600",
    "Atari - 2600": "atari2600",
    "Atari Lynx": "lynx",
    "Atari ST": "atari-st",
    "Atari - ST": "atari-st",
    "Atari Jaguar": "jaguar",
    "Nintendo DS": "ds",
    "Super Nintendo Entertainment System": "snes",
    "Super Famicom": "snes",
    "Nintendo Famicom": "nes",
    "Nintendo Entertainment System": "nes",
    "Nintendo 64": "n64",
    "Game Boy Advance": "gba",
    "Game Boy": "gb",
    "GameCube": "gamecube",
    "Wii": "wii",
    "Switch": "switch",
    "PlayStation 2": "ps2",
    "PlayStation 3": "ps3",
    "PlayStation Vita": "psvita",
    "PlayStationPortable": "psp",
    "PlayStation Portable": "psp",
    "PlayStation": "ps1",
    "CD-i": "cdi",
    "MSX2": "msx",
    "Archimedes": "archimedes",
    "Acorn BBC": "bbc",
    "Acorn Electron": "electron",
    "Bally": "astrocade",
    "WonderSwan Color": "wonderswancolor",
    "WonderSwan": "wonderswan",
    "Amstrad CPC - Games - [DSK]": "cpc6128disk",
    "Amstrad CPC - Games - [CPR]": "gx4000",
    "Apple II": "apple2",
}


def search_tosec_by_md5(md5sum):
    """Retrieve a lutris bundle from the API"""
    if not md5sum:
        return []
    url = settings.SITE_URL + "/api/tosec/games?md5=" + md5sum
    response = http.Request(url, headers={"Content-Type": "application/json"})
    try:
        response.get()
    except http.HTTPError as ex:
        logger.error("Unable to get bundle from API: %s", ex)
        return None
    response_data = response.json
    return response_data["results"]


def scan_folder(folder, extract_archives=False):
    roms = {}
    archives = []
    saves = {}
    checksums = {}
    archive_contents = []
    if extract_archives:
        for filename in os.listdir(folder):
            basename, ext = os.path.splitext(filename)
            if ext not in archive_formats:
                continue
            extract_archive(
                os.path.join(folder, filename),
                os.path.join(folder, basename),
                merge_single=False
            )
            for archive_file in os.listdir(os.path.join(folder, basename)):
                archive_contents.append("%s/%s" % (basename, archive_file))

    for filename in os.listdir(folder) + archive_contents:
        basename, ext = os.path.splitext(filename)
        if ext in archive_formats:
            archives.append(filename)
            continue
        if ext in save_formats:
            saves[basename] = filename
            continue
        if os.path.isdir(os.path.join(folder, filename)):
            continue

        md5sum = get_md5_hash(os.path.join(folder, filename))
        roms[filename] = search_tosec_by_md5(md5sum)
        checksums[md5sum] = filename

    for rom, result in roms.items():
        if not result:
            print("no result for %s" % rom)
            continue
        if len(result) > 1:
            print("More than 1 match for %s", rom)
            continue
        print("Found: %s" % result[0]["name"])
        roms_matched = 0
        renames = {}
        for game_rom in result[0]["roms"]:
            source_file = checksums[game_rom["md5"]]
            dest_file = game_rom["name"]
            renames[source_file] = dest_file
            roms_matched += 1
        if roms_matched == len(result[0]["roms"]):
            for source, dest in renames.items():
                base_name, _ext = os.path.splitext(source)
                dest_base_name, _ext = os.path.splitext(dest)
                if base_name in saves:
                    save_file = saves[base_name]
                    _base_name, ext = os.path.splitext(save_file)
                    os.rename(
                        os.path.join(folder, save_file),
                        os.path.join(folder, dest_base_name + ext)
                    )
                try:
                    os.rename(
                        os.path.join(folder, source),
                        os.path.join(folder, dest)
                    )
                except FileNotFoundError:
                    logger.error("Failed to rename %s to %s", source, dest)


def guess_platform(game):
    category = game["category"]["name"]
    for pattern, platform in PLATFORM_PATTERNS.items():
        if pattern in category:
            return platform


def clean_rom_name(name):
    in_parens = False
    good_index = 0
    for i, c in enumerate(name[::-1], start=1):
        if c in (")", "]"):
            in_parens = True
        if in_parens:
            good_index = i
        if c in ("(", "]"):
            in_parens = False
    name = name[:len(name) - good_index].strip()
    if name.endswith(", The"):
        name = "The " + name[:-5]
    return name
