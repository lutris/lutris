"""GUI dialog for reporting issues"""
import os
import json
from gi.repository import Gtk
from lutris.util.graphics import drivers
from lutris.util.graphics.glxinfo import GlxInfo
from lutris.util.linux import LINUX_SYSTEM

def gather_system_info():
    """Get all system information in a single data structure"""
    system_info = {}
    if drivers.is_nvidia:
        system_info["nvidia_driver"] = drivers.get_nvidia_driver_info()
        system_info["nvidia_gpus"] = [
            drivers.get_nvidia_gpu_info(gpu_id)
            for gpu_id in drivers.get_nvidia_gpu_ids()
        ]
    system_info["gpus"] = [drivers.get_gpu_info(gpu) for gpu in drivers.get_gpus()]
    system_info["env"] = dict(os.environ)
    system_info["missing_libs"] = LINUX_SYSTEM.get_missing_libs()
    system_info["cpus"] = LINUX_SYSTEM.get_cpus()
    system_info["drives"] = LINUX_SYSTEM.get_drives()
    system_info["ram"] = LINUX_SYSTEM.get_ram_info()
    system_info["dist"] = LINUX_SYSTEM.get_dist_info()
    system_info["glxinfo"] = GlxInfo().as_dict()
    return system_info


class BaseApplicationWindow(Gtk.ApplicationWindow):
    """Window used to guide the user through a issue reporting process"""
    def __init__(self, application):
        Gtk.ApplicationWindow.__init__(self, icon_name="lutris", application=application)
        self.application = application
        self.set_show_menubar(False)
        self.set_size_request(420, 420)
        self.set_default_size(600, 480)
        self.set_position(Gtk.WindowPosition.CENTER)


        self.vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            visible=True
        )
        self.vbox.set_margin_top(18)
        self.vbox.set_margin_bottom(18)
        self.vbox.set_margin_right(18)
        self.vbox.set_margin_left(18)
        self.add(self.vbox)
        self.action_buttons = Gtk.Box(spacing=6)
        self.vbox.pack_end(self.action_buttons, False, False, 0)

    def get_action_button(self, label, handler=None, tooltip=None):
        """Returns a button that can be used for the action bar"""
        button = Gtk.Button.new_with_mnemonic(label)
        if handler:
            button.connect("clicked", handler)
        if tooltip:
            button.set_tooltip_text(tooltip)
        return button

    def on_destroy(self, _widget=None):
        self.destroy()


class IssueReportWindow(BaseApplicationWindow):
    def __init__(self, application):
        super().__init__(application)
        self.system_info = gather_system_info()
        print(json.dumps(self.system_info, indent=2))

        # Title label
        self.title_label = Gtk.Label(visible=True)
        self.vbox.add(self.title_label)

        title_label = Gtk.Label()
        title_label.set_markup("<b>Submit an issue</b>")
        self.vbox.add(title_label)
        self.vbox.add(Gtk.HSeparator())

        issue_entry_label = Gtk.Label("Describe the problem you're having. ")
        self.vbox.add(issue_entry_label)

        self.textview = Gtk.TextView()
        self.textview.set_pixels_above_lines(12)
        self.textview.set_pixels_below_lines(12)
        self.textview.set_left_margin(12)
        self.textview.set_right_margin(12)
        self.vbox.pack_start(self.textview, True, True, 0)

        self.action_buttons = Gtk.Box(spacing=6)
        action_buttons_alignment = Gtk.Alignment.new(1, 0, 0, 0)
        action_buttons_alignment.add(self.action_buttons)
        self.vbox.pack_start(action_buttons_alignment, False, True, 0)

        cancel_button = self.get_action_button(
            "C_ancel",
            handler=self.on_destroy
        )
        self.action_buttons.add(cancel_button)

        self.show_all()
