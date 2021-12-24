from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris import runners
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.dialogs import ErrorDialog, QuestionDialog
from lutris.gui.dialogs.download import simple_downloader
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.widgets.utils import ICON_SIZE, get_icon
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
        icon = get_icon(self.runner.name, icon_format='pixbuf', size=ICON_SIZE)
        if icon:
            runner_icon = Gtk.Image(visible=True)
            runner_icon.set_from_pixbuf(icon)
        else:
            runner_icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic", Gtk.IconSize.DND)
            runner_icon.show()
        runner_icon.set_margin_right(12)
        self.pack_start(runner_icon, False, True, 6)

        self.runner_label_box = Gtk.VBox(visible=True)
        self.runner_label_box.set_margin_top(12)

        runner_label = Gtk.Label(visible=True)
        runner_label.set_alignment(0, 0.5)
        runner_label.set_markup("<b>%s</b>" % self.runner.human_name)
        self.runner_label_box.pack_start(runner_label, False, False, 0)

        desc_label = Gtk.Label(visible=True)
        desc_label.set_alignment(0, 0.5)
        desc_label.set_text(self.runner.description)
        self.runner_label_box.pack_start(desc_label, False, False, 0)

        self.pack_start(self.runner_label_box, True, True, 0)

        self.configure_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self.configure_button.set_margin_right(12)
        self.configure_button.connect("clicked", self.on_configure_clicked)
        self.configure_button.show()
        self.pack_start(self.configure_button, False, False, 0)
        if not self.runner.is_installed():
            self.runner_label_box.set_sensitive(False)
        self.action_alignment = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.action_alignment.show()
        self.action_alignment.add(self.get_action_button())
        self.pack_start(self.action_alignment, False, False, 0)

    def get_action_button(self):
        """Return a install or remove button"""
        if self.runner.multiple_versions:
            _button = Gtk.Button.new_from_icon_name("preferences-other-symbolic", Gtk.IconSize.BUTTON)
            _button.get_style_context().add_class("circular")
            _button.connect("clicked", self.on_versions_clicked)
        else:
            if self.runner.is_installed():
                _button = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
                _button.get_style_context().add_class("circular")
                _button.connect("clicked", self.on_remove_clicked)
            else:
                _button = Gtk.Button.new_from_icon_name("system-software-install-symbolic", Gtk.IconSize.BUTTON)
                _button.get_style_context().add_class("circular")
                _button.connect("clicked", self.on_install_clicked)
        _button.show()
        return _button

    def on_versions_clicked(self, widget):
        RunnerInstallDialog(
            _("Manage %s versions") % self.runner.name,
            None,
            self.runner.name
        )
        # connect a runner-installed signal from the above dialog?

    def on_install_clicked(self, widget):
        """Install a runner."""
        logger.debug("Install of %s requested", self.runner)
        try:
            self.runner.install(downloader=simple_downloader)
        except (
            runners.RunnerInstallationError,
            runners.NonInstallableRunnerError,
        ) as ex:
            logger.error(ex)
            ErrorDialog(ex.message)
            return
        if self.runner.is_installed():
            self.emit("runner-installed")
        else:
            logger.error("Runner failed to install")

    def on_configure_clicked(self, widget):
        RunnerConfigDialog(self.runner)

    def on_remove_clicked(self, widget):
        dialog = QuestionDialog(
            {
                "title": _("Do you want to uninstall %s?") % self.runner.human_name,
                "question": _("This will remove <b>%s</b> and all associated data." % self.runner.human_name)

            }
        )
        if Gtk.ResponseType.YES == dialog.result:
            self.runner.uninstall()
            self.emit("runner-removed")

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
