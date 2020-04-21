"""Utility functions for MAME"""
from xml.etree import ElementTree
from lutris.util.system import execute


def write_xml(mame_path, xml_path):
    """Save the output of -listxml to a file"""
    xml_data = execute([mame_path, "-listxml"])
    with open(xml_path, "r") as xml_file:
        xml_file.write(xml_data)


def simplify_manufacturer(manufacturer):
    """Give simplified names for some manufacturers"""
    if manufacturer == "Amstrad plc":
        return "Amstrad"
    if manufacturer == "Commodore Business Machines":
        return "Commodore"
    if manufacturer == "Apple Computer":
        return "Apple"
    return manufacturer


def is_game(machine):
    """Return True if the given machine game is an original arcade game
    Clones return False
    """
    return (
        machine.attrib["isbios"] == "no"
        and machine.attrib["isdevice"] == "no"
        and machine.attrib["runnable"] == "yes"
        and not "cloneof" in machine.attrib
        and not "romof" in machine.attrib
        and not has_software_list(machine)
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
            machine.attrib.get("runnable") == "no"
            or machine.attrib.get("isdevice") == "yes"
            or machine.attrib.get("isbios") == "yes"
            or machine.attrib.get("cloneof")
    ):
        return False
    return has_software_list(machine)


def iter_machines(xml_path, filter_func):
    """Iterate through machine nodes in the MAME XML"""
    root = ElementTree.parse(xml_path).getroot()
    for machine in root:
        if not filter_func(machine):
            continue
        yield machine


def get_machine_info(machine):
    """Return human readable information about a machine node"""
    _info = {
        elem.tag: elem.text
        for elem in machine
        if elem.tag in ("description", "year", "manufacturer")
    }
    _info["manufacturer"] = simplify_manufacturer(_info["manufacturer"])
    return _info


def get_supported_systems(xml_path):
    """Return supported systems (computers and consoles) supported.
    From the full XML list extracted from MAME, filter the systems that are
    runnable, not clones and have the ability to run software.
    """
    return {
        machine.attrib["name"]: get_machine_info(machine)
        for machine in iter_machines(xml_path, is_system)
    }


def get_games(xml_path):
    """Return a list of all games"""
    return {
        machine.attrib["name"]: get_machine_info(machine)
        for machine in iter_machines(xml_path, is_game)
    }
