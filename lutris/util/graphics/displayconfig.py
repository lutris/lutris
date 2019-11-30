"""DBus backed display management for Mutter"""
import dbus


class Output:
    """Representation of a physical display output"""
    def __init__(self, output_info):
        self._output = output_info

    def __repr__(self):
        return "<Output: %s %s (%s)>" % (self.vendor, self.product, self.display_name)

    @property
    def output_id(self):
        """ID of the output"""
        return self._output[0]

    @property
    def winsys_id(self):
        """The low-level ID of this output (XID or KMS handle)"""
        return self._output[1]

    @property
    def current_crtc(self):
        """The CRTC that is currently driving this output,
        or -1 if the output is disabled
        """
        return self._output[2]

    @property
    def crtcs(self):
        """All CRTCs that can control this output"""
        return self._output[3]

    @property
    def name(self):
        """The name of the connector to which the output is attached (like VGA1 or HDMI)"""
        return self._output[4]

    @property
    def modes(self):
        """Valid modes for this output"""
        return [int(mode_id) for mode_id in self._output[5]]

    @property
    def clones(self):
        """Valid clones for this output, ie other outputs that can be assigned
        the same CRTC as this one; if you want to mirror two outputs that don't
        have each other in the clone list, you must configure two different
        CRTCs for the same geometry.
        """
        return self._output[6]

    @property
    def properties(self):
        """Other high-level properties that affect this output; they are not
        necessarily reflected in the hardware.
        """
        return self._output[7]

    @property
    def vendor(self):
        """Vendor name of the output"""
        return str(self._output[7]["vendor"])

    @property
    def product(self):
        """Product name of the output"""
        return str(self._output[7]["product"])

    @property
    def display_name(self):
        """A human readable name of this output, to be shown in the UI"""
        return str(self._output[7]["display-name"])

    @property
    def is_primary(self):
        """Vendor name of the output"""
        return bool(self._output[7]["primary"])


class DisplayMode:
    """Representation of a screen mode (resolution, refresh rate, scaling)"""
    def __init__(self, mode_info):
        self.mode_info = mode_info

    def __str__(self):
        return "%sx%s@%s" % (self.width, self.height, self.frequency)

    def __repr__(self):
        return "<DisplayMode: %sx%s@%s>" % (self.width, self.height, self.frequency)

    def mode_id(self):
        """ID of the mode"""
        return self.mode_info[0]

    @property
    def width(self):
        """width in physical pixels"""
        return self.mode_info[1]

    @property
    def height(self):
        """height in physical pixels"""
        return self.mode_info[2]

    @property
    def frequency(self):
        """refresh rate"""
        return self.mode_info[3]

    @property
    def scale(self):
        """scale preferred as per calculations"""
        return self.mode_info[4]

    @property
    def supported_scale(self):
        """scales supported by this mode"""
        return self.mode_info[5]

    @property
    def properties(self):
        """optional properties"""
        return self.mode_info[6]

    @property
    def is_current(self):
        """Return True if the mode is the current one"""
        return "is-current" in self.properties


class MutterDisplayConfig():
    """Class to interact with the Mutter.DisplayConfig service"""
    namespace = "org.gnome.Mutter.DisplayConfig"
    dbus_path = "/org/gnome/Mutter/DisplayConfig"

    # Methods used in ApplyMonitorConfig
    VERIFY_METHOD = 0
    TEMPORARY_METHOD = 1
    PERSISTENT_METHOD = 2

    def __init__(self):
        session_bus = dbus.SessionBus()
        proxy_obj = session_bus.get_object(self.namespace, self.dbus_path)
        self.interface = dbus.Interface(proxy_obj, dbus_interface=self.namespace)
        self.resources = self.interface.GetResources()
        self.current_state = self.interface.GetCurrentState()
        self.config_serial = self.current_state[0]

    @property
    def serial(self):
        """
        @serial is an unique identifier representing the current state
        of the screen. It must be passed back to ApplyConfiguration()
        and will be increased for every configuration change (so that
        mutter can detect that the new configuration is based on old
        state)
        """
        return self.resources[0]

    @property
    def crtcs(self):
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
        return self.resources[1]

    @property
    def outputs(self):
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
        return self.resources[2]

    @property
    def modes(self):
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
        return self.resources[3]

    @property
    def max_screen_width(self):
        """Maximum width supported"""
        return self.resources[4]

    @property
    def max_screen_height(self):
        """Maximum height supported"""
        return self.resources[5]

    def get_modes(self):
        """Return the available screen modes"""
        _s, monitors, _lm, _p = self.current_state
        _monitor_info, modes, _props = monitors[0]
        return [DisplayMode(mode) for mode in modes]

    def get_current_mode(self):
        """Return the current mode"""
        for mode in self.get_modes():
            if mode.is_current:
                return mode

    def get_mode_for_resolution(self, resolution):
        """Return an appropriate mode for a given resolution"""
        width, height = [int(i) for i in resolution.split("x")]
        for mode in self.get_modes():
            if mode.width == width and mode.height == height:
                return mode

    def get_primary_output(self):
        """Return the primary output"""
        for output in self.get_outputs():
            if output.is_primary:
                return output

    def get_outputs(self):
        """Return the available outputs"""
        return [Output(output) for output in self.outputs]

    def apply_monitors_config(self, display_name, mode, scale=1.0):
        """Set the selected display to the desired resolution"""
        transform = dbus.UInt32(0)
        is_primary = True
        monitors = [
            [
                0,
                0,
                dbus.Double(scale),
                transform,
                is_primary,
                [[dbus.String(str(display_name)), dbus.String(str(mode)), {}]]
            ]
        ]
        self.interface.ApplyMonitorsConfig(
            self.config_serial,
            self.TEMPORARY_METHOD,
            monitors,
            {}
        )


class MutterDisplayManager:
    """Manage displays using the DBus Mutter interface"""

    def __init__(self):
        self.display_config = MutterDisplayConfig()

    def get_display_names(self):
        """Return display names of connected displays"""
        return [
            output.display_name for output in self.display_config.get_outputs()
        ]

    def get_resolutions(self):
        """Return available resolutions"""
        resolutions = [
            "%sx%s" % (mode.width, mode.height)
            for mode in self.display_config.get_modes()
        ]
        return sorted(
            set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True
        )

    def get_current_resolution(self):
        """Return the current resolution for the primary display"""
        current_mode = self.display_config.get_current_mode()
        return current_mode.width, current_mode.height

    def set_resolution(self, resolution):
        """Change the current resolution"""
        if isinstance(resolution, str):
            mode = self.display_config.get_mode_for_resolution(resolution)
            output = self.display_config.get_primary_output()
            self.display_config.apply_monitors_config(output.display_name, mode)
        else:
            for display in resolution:
                mode = self.display_config.get_mode_for_resolution(display.mode)
                self.display_config.apply_monitors_config(display.name, mode)

        # Load a fresh config since the current one has changed
        self.display_config = MutterDisplayConfig()
