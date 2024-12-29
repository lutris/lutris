import json
import os
import shutil

from lutris.settings import CACHE_DIR
from lutris.util import system
from lutris.util.log import logger
from lutris.util.system import get_md5_hash

FIRMWARE_CACHE_PATH = os.path.join(CACHE_DIR, "bios-files.json")


def get_folder_contents(target_directory: str, with_hash: bool = True) -> list:
    """Recursively iterate over a folder content and return its details"""
    folder_content = []
    for path, dir_names, file_names in os.walk(target_directory):
        for dir_name in dir_names:
            dir_path = os.path.join(path, dir_name)
            folder_content.append(
                {
                    "name": dir_path,
                    "date_created": os.path.getctime(dir_path),
                    "date_modified": os.path.getmtime(dir_path),
                    "date_accessed": os.path.getatime(dir_path),
                    "type": "folder",
                }
            )
        for file_name in file_names:
            file_path = os.path.join(path, file_name)
            file_stats = os.stat(file_path)
            file_desc = {
                "name": file_path,
                "size": file_stats.st_size,
                "date_created": file_stats.st_ctime,
                "date_modified": file_stats.st_mtime,
                "date_accessed": file_stats.st_atime,
                "type": "file",
            }
            if with_hash:
                file_desc["md5_hash"] = get_md5_hash(file_path)
            folder_content.append(file_desc)
    return folder_content


def scan_firmware_directory(target_directory: str):
    """Scans a target directory for firmwares and generates/updates the JSON 'firmware cache'
    file with relevant details and hashes for each file within the directory"""

    firmwares_cache_data = json.dumps(get_folder_contents(target_directory, with_hash=True), indent=2)
    with open(FIRMWARE_CACHE_PATH, "w+") as firmwares_cache:
        firmwares_cache.write(firmwares_cache_data)


def get_firmware(target_firmware_name: str, target_firmware_checksum: str, runner_system_path: str):
    """Given a target firmware's name and checksum and the target runner's system directory, searches the
    user's BIOS cache for a firmware matching the checksum and places it under the provided system directory
    and name"""

    if not system.path_exists(FIRMWARE_CACHE_PATH):
        logger.error(f"Firmware {FIRMWARE_CACHE_PATH} not found.")
        return

    with open(FIRMWARE_CACHE_PATH) as bios_cache_data:
        bios_cache = json.load(bios_cache_data)

    for cached_firmware_record in bios_cache:
        # The checksum of the installed firmware we're looking at matches our target
        if cached_firmware_record.get("md5_hash") == target_firmware_checksum:
            system.create_folder(runner_system_path)
            shutil.copyfile(
                cached_firmware_record["name"],
                os.path.join(runner_system_path, target_firmware_name),
            )
            logger.info(f"Firmware {target_firmware_name} found and copied to {runner_system_path}")
