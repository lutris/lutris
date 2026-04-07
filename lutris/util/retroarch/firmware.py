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
            safe_firmware_name = os.path.basename(target_firmware_name)
            if not safe_firmware_name:
                logger.error("Invalid firmware name: %s", target_firmware_name)
                return
            source_path = os.path.realpath(cached_firmware_record["name"])
            destination_path = os.path.realpath(os.path.join(runner_system_path, safe_firmware_name))
            resolved_system = os.path.realpath(runner_system_path)
            if not destination_path.startswith(resolved_system + os.sep):
                logger.error("Firmware destination path is outside system directory: %s", destination_path)
                return
            if not os.path.isfile(source_path):
                logger.error("Cached firmware source does not exist: %s", source_path)
                return
            system.create_folder(runner_system_path)
            shutil.copyfile(source_path, destination_path)
            logger.info(f"Firmware {safe_firmware_name} found and copied to {runner_system_path}")
