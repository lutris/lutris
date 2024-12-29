import json
import os
import shutil

from lutris.settings import CACHE_DIR
from lutris.util import system
from lutris.util.files import get_folder_contents
from lutris.util.log import logger

FIRMWARE_CACHE_PATH = os.path.join(CACHE_DIR, "bios-files.json")


def scan_firmware_directory(target_directory: str):
    """Scans a target directory for firmwares and generates/updates the JSON 'firmware cache'
    file with relevant details and hashes for each file within the directory"""

    with open(FIRMWARE_CACHE_PATH, "w+") as firmwares_cache:
        json.dump(get_folder_contents(target_directory, with_hash=True), firmwares_cache, indent=2)


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
