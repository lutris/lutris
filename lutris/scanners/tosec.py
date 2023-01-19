import os

from lutris import settings
from lutris.util import http
from lutris.util.extract import extract_archive
from lutris.util.log import logger
from lutris.util.system import get_md5_hash

archive_formats = [".zip", ".7z", ".rar", ".gz"]
save_formats = [".srm"]


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

    print(archives)

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
