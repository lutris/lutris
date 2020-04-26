"""Utility functions for MAME"""
# Standard Library
import json
import os
from xml.etree import ElementTree

# Lutris Modules
from lutris import settings
from lutris.util.log import logger

CACHE_DIR = os.path.join(settings.CACHE_DIR, "mame")


def simplify_manufacturer(manufacturer):
    """Give simplified names for some manufacturers"""
    manufacturer_map = {
        "Amstrad plc": "Amstrad",
        "Apple Computer": "Apple",
        "Commodore Business Machines": "Commodore",
    }
    return manufacturer_map.get(manufacturer, manufacturer)


def is_game(machine):
    """Return True if the given machine game is an original arcade game
    Clones return False
    """
    return (
        machine.attrib["isbios"] == "no" and machine.attrib["isdevice"] == "no" and machine.attrib["runnable"] == "yes"
        and "cloneof" not in machine.attrib and "romof" not in machine.attrib and not has_software_list(machine)
    )


def has_software_list(machine):
    """Return True if the machine has an associated software list"""
    _has_software_list = False
    for elem in machine:
        if elem.tag == "device_ref" and elem.attrib["name"] == "software_list":
            _has_software_list = True
    return _has_software_list


def is_system(machine):
    """Given a machine XML tag, return True if it is a computer, console or
    handheld.
    """
    if (
        machine.attrib.get("runnable") == "no" or machine.attrib.get("isdevice") == "yes"
        or machine.attrib.get("isbios") == "yes"
    ):
        return False
    return has_software_list(machine)


def iter_machines(xml_path, filter_func=None):
    """Iterate through machine nodes in the MAME XML"""
    root = ElementTree.parse(xml_path).getroot()
    for machine in root:
        if filter_func and not filter_func(machine):
            continue
        yield machine


def get_machine_info(machine):
    """Return human readable information about a machine node"""
    return {
        "description":
        machine.find("description").text,
        "manufacturer":
        simplify_manufacturer(machine.find("manufacturer").text),
        "year":
        machine.find("year").text,
        "roms": [rom.attrib for rom in machine.findall("rom")],
        "devices": [
            {
                "info": device.attrib,
                "name": "".join([instance.attrib["name"] for instance in device.findall("instance")]),
                "briefname": "".join([instance.attrib["briefname"] for instance in device.findall("instance")]),
                "extensions": [extension.attrib["name"] for extension in device.findall("extension")],
            } for device in machine.findall("device")
        ],
        "driver":
        machine.find("driver").attrib,
    }


def get_supported_systems(xml_path, force=False):
    """Return supported systems (computers and consoles) supported.
    From the full XML list extracted from MAME, filter the systems that are
    runnable, not clones and have the ability to run software.
    """
    systems_cache_path = os.path.join(CACHE_DIR, "systems.json")
    if os.path.exists(systems_cache_path) and not force:
        with open(systems_cache_path, "r") as systems_cache_file:
            try:
                systems = json.load(systems_cache_file)
            except json.JSONDecodeError:
                logger.error("Failed to read systems cache %s", systems_cache_path)
                systems = None
        if systems:
            return systems
    systems = {machine.attrib["name"]: get_machine_info(machine) for machine in iter_machines(xml_path, is_system)}
    with open(systems_cache_path, "w") as systems_cache_file:
        json.dump(systems, systems_cache_file, indent=2)
    return systems


def get_games(xml_path):
    """Return a list of all games"""
    return {machine.attrib["name"]: get_machine_info(machine) for machine in iter_machines(xml_path, is_game)}
