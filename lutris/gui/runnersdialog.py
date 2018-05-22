# -*- coding:Utf-8 -*-
from gi.repository import GObject, Gtk
from lutris import runners, settings
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.runnerinstalldialog import RunnerInstallDialog
from lutris.gui.widgets.utils import get_icon
from lutris.util.system import open_uri
from lutris.util.log import logger


class RunnersDialog(Gtk.Dialog):
    """Dialog to manage the runners."""
    __gsignals__ = {
        "runner-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(use_header_bar=1, **kwargs)

        self.runner_labels = {}

        self.set_title("Manage runners")
        width = int(settings.read_setting('runners_manager_width') or 700)
        height = int(settings.read_setting('runners_manager_height') or 500)
        self.dialog_size = (width, height)
        self.set_default_size(width, height)
        self._vbox = self.get_content_area()
        self._header = self.get_header_bar()

        # Signals
        self.connect('destroy', self.on_destroy)
        self.connect('configure-event', self.on_resize)

        # Scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        self._vbox.pack_start(scrolled_window, True, True, 0)

        # Runner list
        self.runner_list = sorted(runners.__all__)
        self.runner_listbox = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        self.runner_listbox.set_header_func(self._listbox_header_func)

        self.populate_runners()

        scrolled_window.add(self.runner_listbox)

        # Header buttons
        buttons_box = Gtk.Box(spacing=6)

        refresh_button = Gtk.Button.new_from_icon_name('view-refresh-symbolic', Gtk.IconSize.BUTTON)
        refresh_button.props.tooltip_text = 'Refresh runners'
        refresh_button.connect('clicked', self.on_refresh_clicked)
        buttons_box.add(refresh_button)

        open_runner_button = Gtk.Button.new_from_icon_name('folder-symbolic', Gtk.IconSize.BUTTON)
        open_runner_button.props.tooltip_text = 'Open Runners Folder'
        open_runner_button.connect('clicked', self.on_runner_open_clicked)
        buttons_box.add(open_runner_button)
        buttons_box.show_all()
        self._header.add(buttons_box)

        self.show_all()

    @staticmethod
    def _listbox_header_func(row, before):
        if not row.get_header() and before is not None:
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    def get_runner_hbox(self, runner_name):
        # Get runner details
        runner = runners.import_runner(runner_name)()
        platform = ', '.join(sorted(list(set(runner.platforms))))
        description = runner.description

        hbox = Gtk.Box()
        hbox.show()
        # Icon
        icon = get_icon(runner_name)
        icon.show()
        icon.set_alignment(0.5, 0.1)
        hbox.pack_start(icon, False, False, 10)

        # Label
        runner_label = Gtk.Label()
        runner_label.show()
        if not runner.is_installed():
            runner_label.set_sensitive(False)
        runner_label.set_markup(
            "<b>%s</b>\n%s\n <i>Supported platforms : %s</i>" %
            (runner.human_name, description, platform)
        )
        runner_label.set_width_chars(40)
        runner_label.set_max_width_chars(40)
        runner_label.set_property('wrap', True)
        runner_label.set_line_wrap(True)
        runner_label.set_alignment(0.0, 0.1)
        runner_label.set_padding(5, 0)
        self.runner_labels[runner] = runner_label
        hbox.pack_start(runner_label, True, True, 5)

        # Buttons
        self.versions_button = Gtk.Button("Manage versions")
        self.versions_button.set_size_request(120, 30)
        self.versions_button.set_valign(Gtk.Align.CENTER)
        self.versions_button.connect("clicked", self.on_versions_clicked,
                                     runner, runner_label)
        hbox.pack_start(self.versions_button, False, False, 5)

        self.install_button = Gtk.Button("Install")
        self.install_button.set_size_request(80, 30)
        self.install_button.set_valign(Gtk.Align.CENTER)
        self.install_button.connect("clicked", self.on_install_clicked, runner,
                                    runner_label)
        hbox.pack_start(self.install_button, False, False, 5)

        self.configure_button = Gtk.Button("Configure")
        self.configure_button.set_size_request(90, 30)
        self.configure_button.set_valign(Gtk.Align.CENTER)
        self.configure_button.connect("clicked", self.on_configure_clicked,
                                      runner, runner_label)
        hbox.pack_start(self.configure_button, False, False, 5)

        self.set_button_display(runner)

        return hbox

    def populate_runners(self):
        for runner_name in self.runner_list:
            hbox = self.get_runner_hbox(runner_name)
            self.runner_listbox.add(hbox)

    def set_button_display(self, runner):
        if runner.multiple_versions:
            self.versions_button.show()
            self.install_button.hide()
        else:
            self.versions_button.hide()
            self.install_button.show()

        if runner.is_installed():
            self.install_button.hide()

        self.configure_button.show()

    def on_versions_clicked(self, widget, runner, runner_label):
        dlg_title = "Manage %s versions" % runner.name
        versions_dialog = RunnerInstallDialog(dlg_title, self, runner.name)
        versions_dialog.connect('destroy', self.set_install_state,
                                runner, runner_label)

    def on_install_clicked(self, widget, runner, runner_label):
        """Install a runner."""
        if runner.depends_on is not None:
            dependency = runner.depends_on()
            dependency.install()
        try:
            runner.install()
        except (runners.RunnerInstallationError,
                runners.NonInstallableRunnerError) as ex:
            ErrorDialog(ex.message, parent=self)
        if runner.is_installed():
            self.emit('runner-installed')
            widget.hide()
            runner_label.set_sensitive(True)

    def on_configure_clicked(self, widget, runner, runner_label):
        config_dialog = RunnerConfigDialog(runner, parent=self)
        config_dialog.connect('destroy', self.set_install_state,
                              runner, runner_label)

    def on_runner_open_clicked(self, widget):
        open_uri('file://' + settings.RUNNER_DIR)

    def on_refresh_clicked(self, widget):
        for child in self.runner_listbox:
            child.destroy()
        self.populate_runners()

    def on_close_clicked(self, widget):
        self.destroy()

    def set_install_state(self, widget, runner, runner_label):
        if runner.is_installed():
            runner_label.set_sensitive(True)
            self.emit('runner-installed')
        else:
            runner_label.set_sensitive(False)

    def on_resize(self, widget, *args):
        """Store the dialog's new size."""
        self.dialog_size = self.get_size()

    def on_destroy(self, widget):
        # Save window size
        width, height = self.dialog_size
        settings.write_setting('runners_manager_width', width)
        settings.write_setting('runners_manager_height', height)
