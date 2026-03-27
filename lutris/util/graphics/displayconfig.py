"""DBus backed display management for Mutter"""

from collections import namedtuple
from typing import Any

import dbus

from lutris.settings import DEFAULT_RESOLUTION_HEIGHT, DEFAULT_RESOLUTION_WIDTH
from lutris.util.log import logger

DisplayConfig = namedtuple("DisplayConfig", ("monitors", "name", "position", "transform", "primary", "scale"))


class Output:
    """Representation of a physical display output"""

    def __init__(self, output_info: dbus.Struct):
        self._output = output_info

    def __repr__(self) -> str:
        return "<Output: %s %s (%s)>" % (self.vendor, self.product, self.display_name)

    @property
    def output_id(self) -> int:
        """ID of the output"""
        return int(self._output[0])

    @property
    def winsys_id(self) -> int:
        """The low-level ID of this output (XID or KMS handle)"""
        return int(self._output[1])

    @property
    def current_crtc(self) -> int:
        """The CRTC that is currently driving this output,
        or -1 if the output is disabled
        """
        return int(self._output[2])

    @property
    def crtcs(self) -> list[int]:
        """All CRTCs that can control this output"""
        return [int(crtc) for crtc in self._output[3]]

    @property
    def name(self) -> str:
        """The name of the connector to which the output is attached (like VGA1 or HDMI)"""
        return str(self._output[4])

    @property
    def modes(self) -> list[int]:
        """Valid modes for this output"""
        return [int(mode_id) for mode_id in self._output[5]]

    @property
    def clones(self) -> list[int]:
        """Valid clones for this output, ie other outputs that can be assigned
        the same CRTC as this one; if you want to mirror two outputs that don't
        have each other in the clone list, you must configure two different
        CRTCs for the same geometry.
        """
        return [int(clone) for clone in self._output[6]]

    @property
    def properties(self) -> dict[str, Any]:
        """Other high-level properties that affect this output; they are not
        necessarily reflected in the hardware.
        """
        return dict(self._output[7])

    @property
    def vendor(self) -> str:
        """Vendor name of the output"""
        return str(self._output[7]["vendor"])

    @property
    def product(self) -> str:
        """Product name of the output"""
        return str(self._output[7]["product"])

    @property
    def display_name(self) -> str:
        """A human readable name of this output, to be shown in the UI"""
        return str(self._output[7]["display-name"])

    @property
    def is_primary(self) -> bool:
        """True if the output is the primary one"""
        return bool(self._output[7]["primary"])


class DisplayMode:
    """Representation of a screen mode (resolution, refresh rate)"""

    def __init__(self, mode_info: dbus.Struct):
        self.mode_info = mode_info

    def __str__(self) -> str:
        return "%sx%s@%s" % (self.width, self.height, self.frequency)

    def __repr__(self) -> str:
        return "<DisplayMode: %sx%s@%s>" % (self.width, self.height, self.frequency)

    @property
    def id(self) -> str:  # pylint: disable=invalid-name
        """ID of the mode"""
        return str(self.mode_info[0])

    @property
    def winsys_id(self) -> str:
        """the low-level ID of this mode"""
        return str(self.mode_info[1])

    @property
    def width(self) -> int:
        """width in physical pixels"""
        return int(self.mode_info[2])

    @property
    def height(self) -> int:
        """height in physical pixels"""
        return int(self.mode_info[3])

    @property
    def frequency(self) -> str:
        """refresh rate"""
        return str(self.mode_info[4])

    @property
    def flags(self) -> int:
        """mode flags as defined in xf86drmMode.h and randr.h"""
        return int(self.mode_info[5])


class CRTC:
    """A CRTC (CRT controller) is a logical monitor, ie a portion of the
    compositor coordinate space. It might correspond to multiple monitors, when
    in clone mode, but not that it is possible to implement clone mode also by
    setting different CRTCs to the same coordinates.
    """

    def __init__(self, crtc_info: dbus.Struct):
        self.crtc_info = crtc_info

    def __repr__(self) -> str:
        return "%s %s %s" % (self.id, self.geometry_str, self.current_mode)

    @property
    def id(self) -> str:  # pylint: disable=invalid-name
        """The ID in the API of this CRTC"""
        return str(self.crtc_info[0])

    @property
    def winsys_id(self) -> int:
        """the low-level ID of this CRTC
        (which might be a XID, a KMS handle or something entirely different)"""
        return int(self.crtc_info[1])

    @property
    def geometry_str(self) -> str:
        """Return a human readable representation of the geometry"""
        return "%dx%d%s%d%s%d" % (
            self.geometry[0],
            self.geometry[1],
            "" if self.geometry[2] < 0 else "+",
            self.geometry[2],
            "" if self.geometry[3] < 0 else "+",
            self.geometry[3],
        )

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        """The geometry of this CRTC
        (might be invalid if the CRTC is not in use)
        """
        return (int(self.crtc_info[2]), int(self.crtc_info[3]), int(self.crtc_info[4]), int(self.crtc_info[5]))

    @property
    def current_mode(self) -> int:
        """The current mode of the CRTC, or -1 if this CRTC is not used
        Note: the size of the mode will always correspond to the width
        and height of the CRTC"""
        return int(self.crtc_info[6])

    @property
    def current_transform(self) -> str:
        """The current transform (espressed according to the wayland protocol)"""
        return str(self.crtc_info[7])

    @property
    def transforms(self) -> str:
        """All possible transforms"""
        return str(self.crtc_info[8])

    @property
    def properties(self) -> str:
        """Other high-level properties that affect this CRTC;
        they are not necessarily reflected in the hardware.
        No property is specified in this version of the API.
        """
        return str(self.crtc_info[9])


class MonitorMode(DisplayMode):
    """Represents a mode given by a Monitor instance
    In addition to DisplayMode objects, this gives acces to the current scaling
    used and some additional properties like is_current.
    """

    @property
    def width(self) -> int:
        """width in physical pixels"""
        return int(self.mode_info[1])

    @property
    def height(self) -> int:
        """height in physical pixels"""
        return int(self.mode_info[2])

    @property
    def frequency(self) -> str:
        """refresh rate"""
        return str(self.mode_info[3])

    @property
    def scale(self) -> float:
        """scale preferred as per calculations"""
        return float(self.mode_info[4])

    @property
    def supported_scale(self) -> list[float]:
        """scales supported by this mode"""
        return [float(scale) for scale in self.mode_info[5]]

    @property
    def properties(self) -> dict[str, Any]:
        """Additional properties"""
        return dict(self.mode_info[6])

    @property
    def is_current(self) -> bool:
        """Return True if the mode is the current one"""
        return "is-current" in self.properties


class Monitor:
    """A physical monitor"""

    def __init__(self, monitor: dbus.Struct):
        self._monitor = monitor

    def get_current_mode(self) -> MonitorMode | None:
        """Return the current mode"""
        for mode in self.get_modes():
            if mode.is_current:
                return mode
        return None

    def get_modes(self) -> list[MonitorMode]:
        """Return available modes"""
        return [MonitorMode(mode) for mode in self._monitor[1]]

    def get_mode_for_resolution(self, resolution: str) -> MonitorMode | None:
        """Return an appropriate mode for a given resolution"""
        width, height = [int(i) for i in resolution.split("x")]
        for mode in self.get_modes():
            if mode.width == width and mode.height == height:
                return mode
        return None

    @property
    def name(self) -> str:
        """Name of the connector"""
        return str(self._monitor[0][0])

    @property
    def vendor(self) -> str:
        """Manufacturer of the monitor"""
        return str(self._monitor[0][1])

    @property
    def model(self) -> str:
        """Model name of the monitor"""
        return str(self._monitor[0][2])

    @property
    def serial_number(self) -> str:
        """Serial number"""
        return str(self._monitor[0][3])

    @property
    def is_underscanning(self) -> bool:
        """Return true if the monitor is underscanning"""
        return bool(self._monitor[2]["is-underscanning"])

    @property
    def is_builtin(self) -> bool:
        """Return true if the display is builtin the machine (a laptop or a tablet)"""
        return bool(self._monitor[2]["is-builtin"])

    @property
    def display_name(self) -> str:
        """Human readable name of the display"""
        return str(self._monitor[2]["display-name"])


class LogicalMonitor:
    """A logical monitor. Similar to CRTCs but logical monitors also contain
    scaling information.
    """

    def __init__(self, lm_info: dbus.Struct, monitors: list[Monitor]):
        self._lm = lm_info
        self._monitors = monitors

    @property
    def position(self) -> tuple[int, int]:
        """Return the position of the monitor"""
        return int(self._lm[0]), int(self._lm[1])

    @property
    def scale(self) -> float:
        """Scale"""
        return float(self._lm[2])

    @property
    def transform(self) -> int:
        """Transforms

        Possible transform values:
        0: normal
        1: 90°
        2: 180°
        3: 270°
        4: flipped
        5: 90° flipped
        6: 180° flipped
        7: 270° flipped
        """
        return int(self._lm[3])

    @property
    def primary(self) -> bool:
        """True if this is the primary logical monitor"""
        return bool(self._lm[4])

    def _get_monitor_for_connector(self, connector: str) -> Monitor | None:
        """Return a Monitor instance from its connector name"""
        for monitor in self._monitors:
            if monitor.name == str(connector):
                return monitor
        return None

    @property
    def monitors(self) -> list[Monitor]:
        """Monitors displaying that logical monitor"""
        monitors = [self._get_monitor_for_connector(m[0]) for m in self._lm[5]]
        return [monitor for monitor in monitors if monitor]

    @property
    def properties(self) -> dict[str, Any]:
        """Possibly other properties"""
        return dict(self._lm[6])

    def get_config(self) -> DisplayConfig:
        """Export the current configuration so it can be stored then reapplied later"""

        def monitor_config(monitor: Monitor) -> tuple[str, str]:
            current_mode = monitor.get_current_mode()
            if not current_mode:
                raise RuntimeError(f"Invalid mode for monitor {monitor.name}")
            return (monitor.name, current_mode.id)

        monitors = [monitor_config(monitor) for monitor in self.monitors]
        return DisplayConfig(monitors, self.monitors[0].name, self.position, self.transform, self.primary, self.scale)


class DisplayState:
    """Snapshot of a display configuration at a given time"""

    def __init__(self, interface: dbus.Interface):
        self.interface = interface
        self._state = self.load_state()

    def load_state(self) -> dbus.Struct:
        """Return current state from dbus interface"""
        return self.interface.GetCurrentState()

    @property
    def serial(self) -> int:
        """Configuration serial"""
        return int(self._state[0])

    @property
    def monitors(self) -> list[Monitor]:
        """Available monitors"""
        return [Monitor(monitor) for monitor in self._state[1]]

    @property
    def logical_monitors(self) -> list[LogicalMonitor]:
        """Current logical monitor configuration"""
        return [LogicalMonitor(l_m, self.monitors) for l_m in self._state[2]]

    @property
    def properties(self) -> dict[str, Any]:
        """Display configuration properties"""
        return dict(self._state[3])

    def get_primary_logical_monitor(self) -> LogicalMonitor | None:
        """Return the primary logical monitor"""
        for lm in self.logical_monitors:
            if lm.primary:
                return lm
        return None

    def get_primary_monitor(self) -> Monitor:
        """Returns the first physical monitor on the primary logical monitor."""
        lm = self.get_primary_logical_monitor()
        if lm:
            return lm.monitors[0]
        return self.monitors[0]

    def get_current_mode(self) -> MonitorMode | None:
        """Return the current mode"""
        return self.get_primary_monitor().get_current_mode()


class MutterDisplayConfig:
    """Class to interact with the Mutter.DisplayConfig service"""

    namespace = "org.gnome.Mutter.DisplayConfig"
    dbus_path = "/org/gnome/Mutter/DisplayConfig"

    # Methods used in ApplyMonitorConfig
    VERIFY_METHOD = 0
    TEMPORARY_METHOD = 1
    PERSISTENT_METHOD = 2

    def __init__(self) -> None:
        session_bus = dbus.SessionBus()
        proxy_obj = session_bus.get_object(self.namespace, self.dbus_path)
        self.interface = dbus.Interface(proxy_obj, dbus_interface=self.namespace)
        self.resources = self.interface.GetResources()
        self.current_state = DisplayState(self.interface)

    @property
    def serial(self) -> int:
        """
        @serial is an unique identifier representing the current state
        of the screen. It must be passed back to ApplyConfiguration()
        and will be increased for every configuration change (so that
        mutter can detect that the new configuration is based on old
        state)
        """
        return int(self.resources[0])

    @property
    def crtcs(self) -> list[CRTC]:
        """
        A CRTC (CRT controller) is a logical monitor, ie a portion
        of the compositor coordinate space. It might correspond
        to multiple monitors, when in clone mode, but not that
        it is possible to implement clone mode also by setting different
        CRTCs to the same coordinates.

        The number of CRTCs represent the maximum number of monitors
        that can be set to expand and it is a HW constraint; if more
        monitors are connected, then necessarily some will clone. This
        is complementary to the concept of the encoder (not exposed in
        the API), which groups outputs that necessarily will show the
        same image (again a HW constraint).

        A CRTC is represented by a DBus structure with the following
        layout:
        * u ID: the ID in the API of this CRTC
        * x winsys_id: the low-level ID of this CRTC (which might
                    be a XID, a KMS handle or something entirely
                    different)
        * i x, y, width, height: the geometry of this CRTC
                                (might be invalid if the CRTC is not in
                                use)
        * i current_mode: the current mode of the CRTC, or -1 if this
                        CRTC is not used
                        Note: the size of the mode will always correspond
                        to the width and height of the CRTC
        * u current_transform: the current transform (espressed according
                            to the wayland protocol)
        * au transforms: all possible transforms
        * a{sv} properties: other high-level properties that affect this
                            CRTC; they are not necessarily reflected in
                            the hardware.
                            No property is specified in this version of the API.

        Note: all geometry information refers to the untransformed
        display.
        """
        return [CRTC(crtc) for crtc in self.resources[1]]

    @property
    def outputs(self) -> list[Output]:
        """
        An output represents a physical screen, connected somewhere to
        the computer. Floating connectors are not exposed in the API.
        An output is a DBus struct with the following fields:
        * u ID: the ID in the API
        * x winsys_id: the low-level ID of this output (XID or KMS handle)
        * i current_crtc: the CRTC that is currently driving this output,
                          or -1 if the output is disabled
        * au possible_crtcs: all CRTCs that can control this output
        * s name: the name of the connector to which the output is attached
                  (like VGA1 or HDMI)
        * au modes: valid modes for this output
        * au clones: valid clones for this output, ie other outputs that
                     can be assigned the same CRTC as this one; if you
                     want to mirror two outputs that don't have each other
                     in the clone list, you must configure two different
                     CRTCs for the same geometry
        * a{sv} properties: other high-level properties that affect this
                            output; they are not necessarily reflected in
                            the hardware.
                            Known properties:
                            - "vendor" (s): (readonly) the human readable name
                                            of the manufacturer
                            - "product" (s): (readonly) the human readable name
                                             of the display model
                            - "serial" (s): (readonly) the serial number of this
                                            particular hardware part
                            - "display-name" (s): (readonly) a human readable name
                                                  of this output, to be shown in the UI
                            - "backlight" (i): (readonly, use the specific interface)
                                               the backlight value as a percentage
                                               (-1 if not supported)
                            - "primary" (b): whether this output is primary
                                             or not
                            - "presentation" (b): whether this output is
                                                  for presentation only
                            Note: properties might be ignored if not consistenly
                            applied to all outputs in the same clone group. In
                            general, it's expected that presentation or primary
                            outputs will not be cloned.
        """
        return [Output(output) for output in self.resources[2]]

    @property
    def modes(self) -> list[DisplayMode]:
        """
        A mode represents a set of parameters that are applied to
        each output, such as resolution and refresh rate. It is a separate
        object so that it can be referenced by CRTCs and outputs.
        Multiple outputs in the same CRTCs must all have the same mode.
        A mode is exposed as:
        * u ID: the ID in the API
        * x winsys_id: the low-level ID of this mode
        * u width, height: the resolution
        * d frequency: refresh rate
        * u flags: mode flags as defined in xf86drmMode.h and randr.h

        Output and modes are read-only objects (except for output properties),
        they can change only in accordance to HW changes (such as hotplugging
        a monitor), while CRTCs can be changed with ApplyConfiguration().

        XXX: actually, if you insist enough, you can add new modes
        through xrandr command line or the KMS API, overriding what the
        kernel driver and the EDID say.
        Usually, it only matters with old cards with broken drivers, or
        old monitors with broken EDIDs, but it happens more often with
        projectors (if for example the kernel driver doesn't add the
        640x480 - 800x600 - 1024x768 default modes). Probably something
        that we need to handle in mutter anyway.
        """
        return [DisplayMode(mode) for mode in self.resources[3]]

    @property
    def max_screen_width(self) -> int:
        """Maximum width supported"""
        return int(self.resources[4])

    @property
    def max_screen_height(self) -> int:
        """Maximum height supported"""
        return int(self.resources[5])

    def get_mode_for_resolution(self, resolution: str) -> DisplayMode | None:
        """Return an appropriate mode for a given resolution"""
        width, height = [int(i) for i in resolution.split("x")]
        for mode in self.modes:
            if mode.width == width and mode.height == height:
                return mode
        return None

    def get_primary_logical_monitor(self) -> LogicalMonitor | None:
        """Return the primary logical monitor"""
        return self.current_state.get_primary_logical_monitor()

    def get_primary_monitor(self) -> Monitor:
        """Returns the first physical monitor on the primary logical monitor."""
        return self.current_state.get_primary_monitor()

    def apply_monitors_config(self, display_configs: list[DisplayConfig]) -> None:
        """Set the selected display to the desired resolution"""
        # Reload resources
        if not display_configs:
            logger.error("No display config given, not applying anything")
            return
        self.resources = self.interface.GetResources()
        self.current_state = DisplayState(self.interface)
        monitors_config = [
            [
                config.position[0],
                config.position[1],
                dbus.Double(config.scale),
                dbus.UInt32(config.transform),
                config.primary,
                [
                    [dbus.String(str(display_name)), dbus.String(str(mode)), {}]
                    for display_name, mode in config.monitors
                ],
            ]
            for config in display_configs
        ]
        self.interface.ApplyMonitorsConfig(self.current_state.serial, self.TEMPORARY_METHOD, monitors_config, {})


class MutterDisplayManager:
    """Manage displays using the DBus Mutter interface"""

    def __init__(self) -> None:
        self.display_config = MutterDisplayConfig()

    def get_config(self) -> list[DisplayConfig]:
        """Return the current configuration for each logical monitor"""
        return [logical_monitor.get_config() for logical_monitor in self.display_config.current_state.logical_monitors]

    def get_display_names(self) -> list[str]:
        """Return display names of connected displays"""
        return [output.display_name for output in self.display_config.outputs]

    def get_resolutions(self) -> list[str]:
        """Return available resolutions"""
        resolutions = ["%sx%s" % (mode.width, mode.height) for mode in self.display_config.modes]
        if not resolutions:
            logger.error("Could not generate resolution list")
            return ["%sx%s" % (DEFAULT_RESOLUTION_WIDTH, DEFAULT_RESOLUTION_HEIGHT)]
        return sorted(set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True)

    def get_current_resolution(self) -> tuple[str, str]:
        """Return the current resolution for the primary display"""
        logger.debug("Retrieving current resolution")
        current_mode = self.display_config.current_state.get_current_mode()
        if not current_mode:
            logger.error("Could not retrieve the current display mode")
            return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)
        return str(current_mode.width), str(current_mode.height)

    def set_resolution(self, resolution: str | list[DisplayConfig]) -> None:
        """Change the current resolution"""
        if isinstance(resolution, str):
            monitor = self.display_config.get_primary_monitor()
            mode = monitor.get_mode_for_resolution(resolution)
            if not mode:
                logger.error("Could not find  valid mode for %s", resolution)
                return
            config = [DisplayConfig([(monitor.name, mode.id)], monitor.name, (0, 0), 0, True, 1.0)]
            self.display_config.apply_monitors_config(config)
        elif resolution:
            self.display_config.apply_monitors_config(resolution)
        else:
            return

        # Load a fresh config since the current one has changed
        self.display_config = MutterDisplayConfig()
