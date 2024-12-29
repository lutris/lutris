import json
import os
import shutil

from lutris.config import LutrisConfig
from lutris.settings import CACHE_DIR
from lutris.util import system
from lutris.util.log import logger
from lutris.util.system import get_md5_hash

FIRMWARE_CACHE_PATH = os.path.join(CACHE_DIR, "bios-files.json")


def scan_firmware_directory(target_directory: str):
    """Scans a target directory for firmwares and generates/updates the JSON 'firmware cache'
    file with relevant details and hashes for each file within the directory"""
    firmwares = []

    for path, _dir_names, file_names in os.walk(target_directory):
        for file_name in file_names:
            file_path = f"{path}/{file_name}"

            if os.access(file_path, os.R_OK):
                bios_file = {}
                bios_file["name"] = file_name
                bios_file["filepath"] = file_path
                bios_file["size"] = os.path.getsize(file_path)
                bios_file["date_created"] = os.path.getctime(file_path)
                bios_file["date_modified"] = os.path.getmtime(file_path)
                bios_file["md5_hash"] = get_md5_hash(file_path)

                firmwares.append(bios_file)

    firmwares_cache_data = json.dumps(firmwares, indent=2)
    with open(FIRMWARE_CACHE_PATH, "w+") as firmwares_cache:
        firmwares_cache.write(firmwares_cache_data)


def get_firmware(target_firmware_name: str, target_firmware_checksum: str, runner_system_path: str):
    """Given a target firmware's name and checksum and the target runner's system directory, searches the
    user's BIOS cache for a firmware matching the checksum and places it under the provided system directory
    and name"""
    # Check that this user has a BIOS cache file
    if system.path_exists(FIRMWARE_CACHE_PATH):
        # Read the BIOS cache file
        with open(FIRMWARE_CACHE_PATH) as bios_cache_data:
            # Parse JSON contents of BIOS cache file into a usable array of "firmware objects"
            bios_cache = json.load(bios_cache_data)
            # For each firmware the user has
            for cached_firmware_record in bios_cache:
                # If the checksum of the installed firmware we're looking at matches our target
                if cached_firmware_record["md5_hash"] == target_firmware_checksum:
                    lutris_config = LutrisConfig()
                    bios_path = lutris_config.raw_system_config["bios_path"]
                    system.create_folder(runner_system_path)
                    shutil.copyfile(
                        f"{bios_path}/{cached_firmware_record['name']}",
                        f"{runner_system_path}/{target_firmware_name}",
                    )
    else:
        logger.error(f"""Firmware {target_firmware_name} could not be found and no firmware cache file was found. Try
        updating BIOS folder directory to a valid directory""")
