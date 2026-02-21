"""Add, remove and configure runners"""

from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris.gui.config.create_runner_config_dialog import EditRunnerConfigDialog


class AddRunnerConfigBox(Gtk.Box):
    """Create New Runner Section"""

    __gsignals__ = {"show-created": (GObject.SIGNAL_RUN_FIRST, None, (Gtk.Window,))}

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, margin=12, spacing=6, **kwargs)

        self.label = Gtk.Label(visible=True)
        self.label.set_markup(f"<b>{_('Add runner config')}</b>")
        self.label.set_alignment(0, 0.5)
        self.pack_start(self.label, True, True, 0)

        self.description_label = Gtk.Label(visible=True)
        self.description_label.set_markup(_("Create a new runner config for Lutris"))
        self.description_label.set_line_wrap(True)
        self.description_label.set_alignment(0, 0.5)
        self.pack_start(self.description_label, True, True, 0)

        self.add_runner_config_button = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        self.add_runner_config_button.connect("clicked", self.on_add_runner_config)
        self.add_runner_config_button.set_tooltip_text(_("Create Runner config"))
        self.add_runner_config_button.get_style_context().add_class("circular")
        self.add_runner_config_button.show()
        self.pack_start(self.add_runner_config_button, False, False, 0)

    def on_add_runner_config(self, widget):
        try:
            window = self.get_toplevel()
            application = window.get_application()
            create_runner_dialog = application.show_window(EditRunnerConfigDialog, parent=window)
            self.emit("show-created", create_runner_dialog)
        except RuntimeError as e:
            raise RuntimeError("Cannot open create runner window") from e
