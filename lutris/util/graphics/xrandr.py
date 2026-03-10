"""XrandR based display management"""

import re
import subprocess
from collections import namedtuple

from lutris.settings import DEFAULT_RESOLUTION_HEIGHT, DEFAULT_RESOLUTION_WIDTH
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.system import read_process_output

Output = namedtuple("Output", ("name", "mode", "position", "rotation", "primary", "rate", "preferred_mode"))


def _get_vidmodes():
    """Return video modes from XrandR"""
    xrandr_output = read_process_output([LINUX_SYSTEM.get("xrandr")]).split("\n")
    logger.debug("Retrieving %s video modes from XrandR", len(xrandr_output))
    return xrandr_output


def get_outputs() -> list[Output]:
    """Parse xrandr output and return one Output per active connected display.

    Each Output captures the connector name, current mode (resolution), position,
    rotation, whether it is the primary display, refresh rate, and EDID-preferred
    mode (which on recent XWayland with fractional scaling is the physical resolution,
    while the current mode may be an upscaled virtual canvas)."""
    outputs: list[Output] = []
    logger.debug("Retrieving display outputs")
    vid_modes = _get_vidmodes()
    if not vid_modes:
        logger.error("xrandr didn't return anything")
        return []

    name = position = rotate = current_mode = preferred_mode = rate = None
    primary = False

    def flush():
        if name and current_mode and position:
            outputs.append(
                Output(
                    name=name,
                    mode=current_mode,
                    position=position,
                    rotation=rotate,
                    primary=primary,
                    rate=rate,
                    preferred_mode=preferred_mode,
                )
            )

    for line in vid_modes:
        fields = line.split()
        if not fields:
            continue
        if "connected" in fields[1:] and len(fields) >= 4:
            flush()
            current_mode = preferred_mode = rate = name = position = rotate = None
            primary = False
            try:
                connected_index = fields.index("connected", 1)
                candidate_name = " ".join(fields[:connected_index])
                data_fields = fields[connected_index + 1 :]
                if data_fields[0] == "primary":
                    primary = True
                    data_fields = data_fields[1:]
                geometry, rotate, *_ = data_fields
                if geometry.startswith("("):  # Screen turned off, no geometry
                    continue
                if rotate.startswith("("):  # Screen not rotated, no need to include
                    rotate = "normal"
                _, x_pos, y_pos = geometry.split("+")
                position = "{x_pos}x{y_pos}".format(x_pos=x_pos, y_pos=y_pos)
                name = candidate_name
            except ValueError as ex:
                logger.error(
                    "Unhandled xrandr line %s, error: %s. Please send your xrandr output to the dev team", line, ex
                )
                continue
        elif name and line.startswith("  ") and re.match(r"\s+\d+x\d+", line):
            mode = fields[0]
            for number in fields[1:]:
                if "*" in number:
                    current_mode = mode
                    rate = number.rstrip("*+")
                if "+" in number and preferred_mode is None:
                    preferred_mode = mode

    flush()
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
        outputs = get_outputs()
        if not outputs:
            logger.error("Unable to find the current resolution from xrandr output")
            return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)
        primary = next((o for o in outputs if o.primary), None) or outputs[0]
        mode = primary.mode
        from lutris.util.display import is_display_x11  # import here to avoid circular import

        # This trick will only work on very recent (2026) XWayland implementations; on
        # older ones the preferred mode and mode are the same anyway. But it's no worse
        # than ignoring the issue, and when supported, the preferred mode is the physical
        # resolution instead of the rendering buffer's resolution (which may be scaled).
        if not is_display_x11() and primary.preferred_mode and primary.preferred_mode != mode:
            mode = primary.preferred_mode
        return mode.split("x")

    @staticmethod
    def set_resolution(resolution):
        """Change the current resolution"""
        change_resolution(resolution)

    @staticmethod
    def get_config():
        """Return the current display configuration"""
        return get_outputs()
