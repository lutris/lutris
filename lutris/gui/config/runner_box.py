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
        self.pack_start(self.configure_button, False, False, 0)
        if not self.runner.is_installed():
            self.runner_label_box.set_sensitive(False)
        self.configure_button.show()
        self.action_alignment = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.action_alignment.show()
        self.action_alignment.add(self.get_action_button())
        self.pack_start(self.action_alignment, False, False, 0)

    # Fixed width for all action buttons so they don't shift the configure button beside them.
    ACTION_BUTTON_WIDTH = 36

    def _make_action_button(self, icon_name, callback):
        """Create a circular icon button wired to a callback."""
        button = Gtk.Button.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        button.get_style_context().add_class("circular")
        button.set_size_request(self.ACTION_BUTTON_WIDTH, -1)
        button.connect("clicked", callback)
        button.show()
        return button

    def get_action_button(self):
        """Return an install or remove button"""
        if self.runner.multiple_versions:
            return self._make_action_button("system-software-install-symbolic", self.on_versions_clicked)
        if self.runner.can_uninstall():
            return self._make_action_button("edit-delete-symbolic", self.on_remove_clicked)
        if self.runner.is_suppressed():
            return self._make_action_button("system-software-install-symbolic", self.on_unsuppress_clicked)
        if self.runner.is_installed(suppress_allowed=False, flatpak_allowed=False):
            # Installed externally via system PATH (e.g. linux, system wine) — offer to suppress
            return self._make_action_button("edit-delete-symbolic", self.on_suppress_clicked)
        if self.runner.is_installed(suppress_allowed=False):
            # Only installed via Flatpak — offer install (internal) or suppress via popover
            return self._get_flatpak_popover_button()
        return self._make_action_button("system-software-install-symbolic", self.on_install_clicked)

    def _get_flatpak_popover_button(self):
        """Return a menu button with a popover offering to install the internal
        version or to suppress (hide) the Flatpak-only runner."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        vbox.set_border_width(6)
        vbox.set_spacing(3)

        install_btn = Gtk.ModelButton(visible=True, text=_("Install Lutris version"))
        install_btn.connect("clicked", self.on_install_clicked)
        vbox.pack_start(install_btn, False, False, 0)

        suppress_btn = Gtk.ModelButton(visible=True, text=_("Hide Flatpak version"))
        suppress_btn.connect("clicked", self.on_suppress_clicked)
        vbox.pack_start(suppress_btn, False, False, 0)

        popover = Gtk.Popover(child=vbox)

        menu_button = Gtk.MenuButton(visible=True)
        menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu_button.set_size_request(self.ACTION_BUTTON_WIDTH, -1)
        menu_button.set_popover(popover)
        return menu_button

    def on_versions_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        title = _("Manage %s versions") % self.runner.name
        application.show_window(RunnerInstallDialog, title=title, runner=self.runner, parent=window)

    def on_install_clicked(self, widget):
        """Install a runner."""
        logger.debug("Install of %s requested", self.runner)
        self.runner.install(self.get_toplevel())

        if self.runner.is_installed(suppress_allowed=False):
            self.emit("runner-installed")

    def on_configure_clicked(self, widget):
        window = self.get_toplevel()
        application = window.get_application()
        application.show_window(RunnerConfigDialog, runner=self.runner, parent=window)

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

    def on_suppress_clicked(self, widget):
        dialog = QuestionDialog(
            {
                "parent": self.get_toplevel(),
                "title": _("Do you want to hide %s?") % self.runner.human_name,
                "question": _(
                    "<b>%s</b> is installed outside of Lutris and cannot be removed here.\nHide it from Lutris instead?"
                )
                % self.runner.human_name,
            }
        )
        if Gtk.ResponseType.YES == dialog.result:
            self.runner.suppress()
            self.emit("runner-removed")

    def on_unsuppress_clicked(self, widget):
        self.runner.unsuppress()
        self.emit("runner-installed")

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
