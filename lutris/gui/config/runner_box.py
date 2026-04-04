from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris import runners
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.dialogs import QuestionDialog
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.widgets.scaled_image import ScaledImage
from lutris.util.log import logger


class RunnerBox(Gtk.Box):
    __gsignals__ = {
        "runner-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "runner-removed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, runner_name):
        super().__init__(visible=True)

        self.connect("runner-installed", self.on_runner_installed)
        self.connect("runner-removed", self.on_runner_removed)

        self.set_margin_bottom(12)
        self.set_margin_top(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.runner = runners.import_runner(runner_name)()

        runner_icon = ScaledImage.get_runtime_icon_image(
            self.runner.name, scale_factor=self.get_scale_factor(), visible=True
        )
        runner_icon.set_margin_end(12)
        runner_icon.set_margin_start(6)
        runner_icon.set_margin_end(6)
        self.append(runner_icon)

        self.runner_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        self.runner_label_box.set_margin_top(12)

        runner_label = Gtk.Label(visible=True)
        runner_label.set_halign(Gtk.Align.START)
        runner_label.set_markup("<b>%s</b>" % self.runner.human_name)
        self.runner_label_box.append(runner_label)

        desc_label = Gtk.Label(visible=True)
        desc_label.set_wrap(True)
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_text(self.runner.description)
        self.runner_label_box.append(desc_label)

        self.runner_label_box.set_hexpand(True)
        self.runner_label_box.set_vexpand(True)
        self.append(self.runner_label_box)

        self.configure_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic")
        self.configure_button.set_valign(Gtk.Align.CENTER)
        self.configure_button.set_margin_end(12)
        self.configure_button.connect("clicked", self.on_configure_clicked)
        self.append(self.configure_button)
        if not self.runner.is_installed():
            self.runner_label_box.set_sensitive(False)
        self.action_button_box = Gtk.Box(visible=True)
        self.action_button_box.set_halign(Gtk.Align.CENTER)
        self.action_button_box.set_valign(Gtk.Align.CENTER)
        self.action_button_box.append(self.get_action_button())
        self.append(self.action_button_box)

    def get_action_button(self):
        """Return a install or remove button"""
        if self.runner.multiple_versions:
            _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic")
            _button.add_css_class("circular")
            _button.connect("clicked", self.on_versions_clicked)
        else:
            if self.runner.can_uninstall():
                _button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
                _button.add_css_class("circular")
                _button.connect("clicked", self.on_remove_clicked)
                _button.set_sensitive(self.runner.can_uninstall())
            else:
                _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic")
                _button.add_css_class("circular")
                _button.connect("clicked", self.on_install_clicked)
                _button.set_sensitive(not self.runner.is_installed(flatpak_allowed=False))
        return _button

    def on_versions_clicked(self, widget):
        window = self.get_root()
        application = window.get_application()
        title = _("Manage %s versions") % self.runner.name
        application.show_window(RunnerInstallDialog, title=title, runner=self.runner, parent=window)

    def on_install_clicked(self, widget):
        """Install a runner."""
        logger.debug("Install of %s requested", self.runner)
        self.runner.install(self.get_root())

        if self.runner.is_installed():
            self.emit("runner-installed")

    def on_configure_clicked(self, widget):
        window = self.get_root()
        application = window.get_application()
        application.show_window(RunnerConfigDialog, runner=self.runner, parent=window)

    def on_remove_clicked(self, widget):
        dialog = QuestionDialog(
            {
                "parent": self.get_root(),
                "title": _("Do you want to uninstall %s?") % self.runner.human_name,
                "question": _("This will remove <b>%s</b> and all associated data." % self.runner.human_name),
            }
        )
        if Gtk.ResponseType.YES == dialog.result:

            def on_runner_uninstalled():
                self.emit("runner-removed")

            self.runner.uninstall(on_runner_uninstalled)

    def on_runner_installed(self, widget):
        """Called after the runnner is installed"""
        self.runner_label_box.set_sensitive(True)
        child = self.action_button_box.get_first_child()
        if child:
            child.unparent()
        self.action_button_box.append(self.get_action_button())

    def on_runner_removed(self, widget):
        """Called after the runner is removed"""
        self.runner_label_box.set_sensitive(False)
        child = self.action_button_box.get_first_child()
        if child:
            child.unparent()
        self.action_button_box.append(self.get_action_button())
