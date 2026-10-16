from gettext import gettext as _
from pathlib import Path

from gi.repository import GObject, Gtk

from lutris import runners
from lutris.gui.config.create_runner_config_dialog import EditRunnerConfigDialog, RunnerConfigEditMode
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.dialogs import QuestionDialog
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.widgets.scaled_image import ScaledImage
from lutris.runners.json import SETTING_JSON_RUNNER_DIR
from lutris.runners.yaml import SETTING_YAML_RUNNER_DIR
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
        self.set_margin_left(12)
        self.set_margin_right(12)
        self.runner = runners.import_runner(runner_name)()

        runner_icon = ScaledImage.get_runtime_icon_image(
            self.runner.name, scale_factor=self.get_scale_factor(), visible=True
        )
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

        self.configure_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self.configure_button.set_valign(Gtk.Align.CENTER)
        self.configure_button.set_margin_right(12)
        self.configure_button.connect("clicked", self.on_configure_clicked)
        if not self.runner.is_installed():
            self.runner_label_box.set_sensitive(False)
        self.configure_button.show()
        self.action_alignment = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.action_alignment.show()
        self.action_alignment.add(self.get_action_button())
        self.edit_button = Gtk.Button.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON)

        self.edit_button.set_valign(Gtk.Align.CENTER)
        self.edit_button.set_margin_right(12)

        self.edit_button.connect("clicked", self.on_edit_clicked)
        self.pack_start(self.edit_button, False, False, 0)
        self.pack_start(self.configure_button, False, False, 0)
        self.pack_start(self.action_alignment, False, False, 0)

        # Provide a button to edit the runner if it is existing in the user writable runner directory
        if hasattr(self.runner, "file_path"):
            runner_file_path = Path(self.runner.file_path)
            if (
                runner_file_path
                and runner_file_path.exists()
                and (
                    runner_file_path.is_relative_to(SETTING_JSON_RUNNER_DIR)
                    or runner_file_path.is_relative_to(SETTING_YAML_RUNNER_DIR)
                )
            ):
                self.edit_button.show()

    def get_action_button(self):
        """Return a install or remove button"""
        if self.runner.multiple_versions:
            _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic", Gtk.IconSize.BUTTON)
            _button.get_style_context().add_class("circular")
            _button.connect("clicked", self.on_versions_clicked)
        else:
            if self.runner.can_uninstall():
                _button = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
                _button.get_style_context().add_class("circular")
                _button.connect("clicked", self.on_remove_clicked)
                _button.set_sensitive(self.runner.can_uninstall())
            else:
                _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic", Gtk.IconSize.BUTTON)
                _button.get_style_context().add_class("circular")
                _button.connect("clicked", self.on_install_clicked)
                _button.set_sensitive(not self.runner.is_installed(flatpak_allowed=False))
        _button.show()
        return _button

    def on_versions_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        title = _("Manage %s versions") % self.runner.name
        application.show_window(RunnerInstallDialog, title=title, runner=self.runner, parent=window)

    def on_install_clicked(self, widget):
        """Install a runner."""
        logger.debug("Install of %s requested", self.runner)
        self.runner.install(self.get_toplevel())

        if self.runner.is_installed():
            self.emit("runner-installed")

    def on_configure_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        application.show_window(RunnerConfigDialog, runner=self.runner, parent=window)

    def on_edit_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        create_dialog_window = application.show_window(
            EditRunnerConfigDialog, runner=self.runner, parent=window, edit_mode=RunnerConfigEditMode.UPDATE
        )
        create_dialog_window.connect("runner-saved", self.on_runner_saved)

    def on_runner_saved(self, widget, runner_name):
        self.runner = runners.import_runner(runner_name)()

    def on_remove_clicked(self, widget):
        dialog = QuestionDialog(
            {
                "parent": self.get_toplevel(),
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
        self.action_alignment.get_children()[0].destroy()
        self.action_alignment.add(self.get_action_button())

    def on_runner_removed(self, widget):
        """Called after the runner is removed"""
        self.runner_label_box.set_sensitive(False)
        self.action_alignment.get_children()[0].destroy()
        self.action_alignment.add(self.get_action_button())
