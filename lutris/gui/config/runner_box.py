from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris import runners, settings
from lutris.exceptions import watch_errors
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.dialogs import ErrorDialog, QuestionDialog
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.widgets.scaled_image import ScaledImage
from lutris.util.log import logger


class RunnerBox(Gtk.Box):
    __gsignals__ = {
        "runners-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, runner_name):
        super().__init__(visible=True)

        self.connect("runners-changed", self.on_runners_changed)

        self.set_margin_bottom(12)
        self.set_margin_top(12)
        self.set_margin_left(12)
        self.set_margin_right(12)
        self.runner = runners.import_runner(runner_name)()

        runner_icon = ScaledImage.get_runtime_icon_image(self.runner.name,
                                                         scale_factor=self.get_scale_factor(),
                                                         visible=True)
        runner_icon.set_margin_right(12)
        self.pack_start(runner_icon, False, True, 6)

        self.runner_label_box = Gtk.VBox(visible=True)
        self.runner_label_box.set_margin_top(12)

        runner_label = Gtk.Label(visible=True)
        runner_label.set_alignment(0, 0.5)
        runner_label.set_markup("<b>%s</b>" % self.runner.human_name)
        self.runner_label_box.pack_start(runner_label, False, False, 0)

        desc_label = Gtk.Label(visible=True)
        desc_label.set_line_wrap(True)
        desc_label.set_alignment(0, 0.5)
        desc_label.set_text(self.runner.description)
        self.runner_label_box.pack_start(desc_label, False, False, 0)

        self.pack_start(self.runner_label_box, True, True, 0)

        self.visible_switch = Gtk.Switch(visible=True, valign=Gtk.Align.CENTER)
        if settings.read_bool_setting(runner_name, default=True, section="runners"):
            self.visible_switch.set_active(True)
        self.visible_switch.connect("state-set", self.on_visible_checkbox_changed, runner_name)
        self.visible_switch.set_tooltip_text(_("Visibility in the sidebar"))

        self.pack_start(self.visible_switch, False, False, 12)

        self.configure_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self.configure_button.set_tooltip_text(_("Runner configuration"))
        self.configure_button.set_valign(Gtk.Align.CENTER)
        self.configure_button.set_margin_right(12)
        self.configure_button.connect("clicked", self.on_configure_clicked)
        self.configure_button.show()
        self.pack_start(self.configure_button, False, False, 0)
        self.action_alignment = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.action_alignment.show()
        self.action_alignment.add(self.get_action_button())
        self.pack_start(self.action_alignment, False, False, 0)

        self._update_installation_state()

    def _update_installation_state(self):
        is_installed = self.runner.is_installed()
        self.runner_label_box.set_sensitive(is_installed)
        self.visible_switch.set_visible(is_installed)

    def on_visible_checkbox_changed(self, _widget, state, runner_name):
        """Save the visibility when it is toggled."""
        settings.write_setting(runner_name, state, section="runners")
        self.emit("runners-changed")

    def get_action_button(self):
        """Return an install or remove button"""
        if self.runner.multiple_versions:
            _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic", Gtk.IconSize.BUTTON)
            _button.set_tooltip_text(_("Manage runner versions"))
            _button.get_style_context().add_class("circular")
            _button.connect("clicked", self.on_versions_clicked)
        else:
            if self.runner.can_uninstall():
                _button = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
                _button.set_tooltip_text(_("Remove runner"))
                _button.get_style_context().add_class("circular")
                _button.connect("clicked", self.on_remove_clicked)
                _button.set_sensitive(self.runner.can_uninstall())
            else:
                _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic", Gtk.IconSize.BUTTON)
                _button.set_tooltip_text(_("Remove runner"))
                _button.get_style_context().add_class("circular")
                _button.connect("clicked", self.on_install_clicked)
                _button.set_sensitive(not self.runner.is_installed(flatpak_allowed=False))
        _button.show()
        return _button

    @watch_errors()
    def on_versions_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        title = _("Manage %s versions") % self.runner.name
        application.show_window(RunnerInstallDialog, title=title, runner=self.runner, parent=window)

    @watch_errors()
    def on_install_clicked(self, widget):
        """Install a runner."""
        logger.debug("Install of %s requested", self.runner)
        window = self.get_toplevel()
        try:
            self.runner.install(window)
        except (
            runners.RunnerInstallationError,
            runners.NonInstallableRunnerError,
        ) as ex:
            logger.error(ex)
            ErrorDialog(ex.message, parent=self.get_toplevel())
            return
        if self.runner.is_installed():
            if not self.visible_switch.get_active():
                self.visible_switch.set_active(True)  # raises runners-changed
            else:
                self.emit("runners-changed")
        else:
            ErrorDialog("Runner failed to install", parent=self.get_toplevel())

    @watch_errors()
    def on_configure_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        application.show_window(RunnerConfigDialog, runner=self.runner, parent=window)

    @watch_errors()
    def on_remove_clicked(self, widget):
        dialog = QuestionDialog(
            {
                "parent": self.get_toplevel(),
                "title": _("Do you want to uninstall %s?") % self.runner.human_name,
                "question": _("This will remove <b>%s</b> and all associated data." % self.runner.human_name)
            }
        )
        if Gtk.ResponseType.YES == dialog.result:
            def on_runner_uninstalled():
                self.emit("runners-changed")

            self.runner.uninstall(on_runner_uninstalled)

    @watch_errors()
    def on_runners_changed(self, widget):
        """Called after the runner is installed or removed"""
        self.action_alignment.get_children()[0].destroy()
        self.action_alignment.add(self.get_action_button())
        self._update_installation_state()

    def on_watched_error(self, error):
        ErrorDialog(error, parent=self.get_toplevel())
