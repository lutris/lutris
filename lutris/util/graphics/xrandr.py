"""XrandR based display management"""

import re
import subprocess
from collections import namedtuple

from lutris.settings import DEFAULT_RESOLUTION_HEIGHT, DEFAULT_RESOLUTION_WIDTH
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.system import read_process_output

Output = namedtuple("Output", ("name", "mode", "position", "rotation", "primary", "rate"))


def _get_vidmodes():
    """Return video modes from XrandR"""
    xrandr_output = read_process_output([LINUX_SYSTEM.get("xrandr")]).split("\n")
    logger.debug("Retrieving %s video modes from XrandR", len(xrandr_output))
    return xrandr_output


def get_outputs():  # pylint: disable=too-many-locals
    """Return list of namedtuples containing output 'name', 'geometry',
    'rotation' and whether it is the 'primary' display."""
    outputs = []
    logger.debug("Retrieving display outputs")
    vid_modes = _get_vidmodes()
    position = None
    rotate = None
    primary = None
    name = None
    if not vid_modes:
        logger.error("xrandr didn't return anything")
        return []
    for line in vid_modes:
        fields = line.split()
        if "connected" in fields[1:] and len(fields) >= 4:
            try:
                connected_index = fields.index("connected", 1)
                name_fields = fields[:connected_index]
                name = " ".join(name_fields)
                data_fields = fields[connected_index + 1 :]
                if data_fields[0] == "primary":
                    data_fields = data_fields[1:]
                geometry, rotate, *_ = data_fields
                if geometry.startswith("("):  # Screen turned off, no geometry
                    continue
                if rotate.startswith("("):  # Screen not rotated, no need to include
                    rotate = "normal"
                _, x_pos, y_pos = geometry.split("+")
                position = "{x_pos}x{y_pos}".format(x_pos=x_pos, y_pos=y_pos)
            except ValueError as ex:
                logger.error(
                    "Unhandled xrandr line %s, error: %s. Please send your xrandr output to the dev team", line, ex
                )
                continue
        elif "*" in line:
            mode, *framerates = fields
            for number in framerates:
                if "*" in number:
                    hertz = number[:-2]
                    outputs.append(
                        Output(
                            name=name,
                            mode=mode,
                            position=position,
                            rotation=rotate,
                            primary=primary,
                            rate=hertz,
                        )
                    )
                    break
    return outputs


def turn_off_except(display):
    """Use XrandR to turn off displays except the one referenced by `display`"""
    if not display:
        logger.error("No active display given, no turning off every display")
        return
    for output in get_outputs():
        if output.name != display:
            logger.info("Turning off %s", output[0])
            with subprocess.Popen([LINUX_SYSTEM.get("xrandr"), "--output", output.name, "--off"]) as xrandr:
                xrandr.communicate()


def get_resolutions():
    """Return the list of supported screen resolutions."""
    resolution_list = []
    logger.debug("Retrieving resolution list")
    for line in _get_vidmodes():
        if line.startswith("  "):
            resolution_match = re.match(r".*?(\d+x\d+).*", line)
            if resolution_match:
                resolution_list.append(resolution_match.groups()[0])
    if not resolution_list:
        logger.error("Unable to generate resolution list from xrandr output")
        return ["%sx%s" % (DEFAULT_RESOLUTION_WIDTH, DEFAULT_RESOLUTION_HEIGHT)]
    return sorted(set(resolution_list), key=lambda x: int(x.split("x")[0]), reverse=True)


def change_resolution(resolution):
    """Change display resolution.

    Takes a string for single monitors or a list of displays as returned
    by get_outputs().
    """
    if not resolution:
        logger.warning("No resolution provided")
        return
    if isinstance(resolution, str):
        logger.debug("Switching resolution to %s", resolution)

        if resolution not in get_resolutions():
            logger.warning("Resolution %s doesn't exist.", resolution)
        else:
            output_name = get_outputs()[0].name
            logger.info("Changing resolution on %s to %s", output_name, resolution)
            args = [LINUX_SYSTEM.get("xrandr"), "--output", output_name, "--mode", resolution]
            with subprocess.Popen(args) as xrandr:
                xrandr.communicate()
    else:
        for display in resolution:
            logger.debug("Switching to %s on %s", display.mode, display.name)

            if display.rotation is not None and display.rotation in (
                "normal",
                "left",
                "right",
                "inverted",
            ):
                rotation = display.rotation
            else:
                rotation = "normal"
            logger.info("Switching resolution of %s to %s", display.name, display.mode)
            with subprocess.Popen(
                [
                    LINUX_SYSTEM.get("xrandr"),
                    "--output",
                    display.name,
                    "--mode",
                    display.mode,
                    "--pos",
                    display.position,
                    "--rotate",
                    rotation,
                    "--rate",
                    display.rate,
                ]
            ) as xrandr:
                xrandr.communicate()


class LegacyDisplayManager:  # pylint: disable=too-few-public-methods
    """Legacy XrandR based display manager.
    Does not work on Wayland.
    """

    @staticmethod
    def get_display_names():
        """Return output names from XrandR"""
        return [output.name for output in get_outputs()]

    @staticmethod
    def get_resolutions():
        """Return available resolutions"""
        return get_resolutions()

    @staticmethod
    def get_current_resolution():
        """Return the current resolution for the desktop"""
        for line in _get_vidmodes():
            if line.startswith("  ") and "*" in line:
                resolution_match = re.match(r".*?(\d+x\d+).*", line)
                if resolution_match:
                    return resolution_match.groups()[0].split("x")
        logger.error("Unable to find the current resolution from xrandr output")
        return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)

    @staticmethod
    def set_resolution(resolution):
        """Change the current resolution"""
        change_resolution(resolution)

    @staticmethod
    def get_config():
        """Return the current display configuration"""
        return get_outputs()
