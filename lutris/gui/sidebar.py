import os
from gi.repository import Gtk, Pango, GObject, GdkPixbuf

from lutris import runners
from lutris import platforms
from lutris import pga
from lutris.util import datapath
from lutris.util.log import logger
from lutris.gui.runnerinstalldialog import RunnerInstallDialog
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.runnersdialog import RunnersDialog

TYPE = 0
SLUG = 1
ICON = 2
LABEL = 3
GAMECOUNT = 4


class SidebarRow(Gtk.ListBoxRow):
    def __init__(self, id_, type_, name, icon):
        super().__init__()
        self.type = type_
        self.id = id_
        self.btn_box = None

        self.box = Gtk.Box(spacing=6, margin_start=9, margin_end=9)

        # Construct the left column icon space.
        if icon:
            self.box.add(icon)
        else:
            # Place a spacer if there is no loaded icon.
            icon = Gtk.Box(spacing=6, margin_start=9, margin_end=9)
            self.box.add(icon)

        label = Gtk.Label(label=name, halign=Gtk.Align.START, hexpand=True,
                          margin_top=6, margin_bottom=6,
                          ellipsize=Pango.EllipsizeMode.END)
        self.box.add(label)

        self.add(self.box)

    def _create_button_box(self):
        self.btn_box = Gtk.Box(spacing=3, no_show_all=True, valign=Gtk.Align.CENTER,
                               homogeneous=True)

        # Creation is delayed because only installed runners can be imported
        # and all visible boxes should be installed.
        self.runner = runners.import_runner(self.id)()
        entries = []
        if self.runner.multiple_versions:
            entries.append(('system-software-install-symbolic', 'Manage Versions',
                            self.on_manage_versions))
        if self.runner.runnable_alone:
            entries.append(('media-playback-start-symbolic', 'Run', self.runner.run))
        entries.append(('emblem-system-symbolic', 'Configure', self.on_configure_runner))
        for entry in entries:
            btn = Gtk.Button(tooltip_text=entry[1],
                             relief=Gtk.ReliefStyle.NONE,
                             visible=True)
            image = Gtk.Image.new_from_icon_name(entry[0], Gtk.IconSize.MENU)
            image.show()
            btn.add(image)
            btn.connect('clicked', entry[2])
            self.btn_box.add(btn)

        self.box.add(self.btn_box)

    def on_configure_runner(self, *args):
        RunnerConfigDialog(self.runner, parent=self.get_toplevel())

    def on_manage_versions(self, *args):
        dlg_title = "Manage %s versions" % self.runner.name
        RunnerInstallDialog(dlg_title, self.get_toplevel(), self.runner.name)

    def do_state_flags_changed(self, previous_flags):
        if self.id is not None and self.type == 'runner':
            flags = self.get_state_flags()
            if flags & Gtk.StateFlags.PRELIGHT or flags & Gtk.StateFlags.SELECTED:
                if self.btn_box is None:
                    self._create_button_box()
                self.btn_box.show()
            elif self.btn_box is not None and self.btn_box.get_visible():
                self.btn_box.hide()
        Gtk.ListBoxRow.do_state_flags_changed(self, previous_flags)


class SidebarHeader(Gtk.Box):
    def __init__(self, name):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class('sidebar-header')
        label = Gtk.Label(halign=Gtk.Align.START, hexpand=True, use_markup=True,
                          label='<b>{}</b>'.format(name))
        label.get_style_context().add_class('dim-label')
        box = Gtk.Box(margin_start=9, margin_top=6, margin_bottom=6, margin_right=9)
        box.add(label)
        self.add(box)
        if name == 'Runners':
            manage_runners_button = Gtk.Button.new_from_icon_name('emblem-system-symbolic', Gtk.IconSize.MENU)
            manage_runners_button.props.action_name = 'win.manage-runners'
            manage_runners_button.props.relief = Gtk.ReliefStyle.NONE
            manage_runners_button.get_style_context().add_class('sidebar-button')
            box.add(manage_runners_button)
        self.add(Gtk.Separator())
        self.show_all()


class SidebarListBox(Gtk.ListBox):
    __gtype_name__ = 'LutrisSidebar'

    def __init__(self):
        super().__init__()
        self.get_style_context().add_class('sidebar')
        self.installed_runners = []
        self.active_platforms = pga.get_used_platforms()
        self.runners = sorted(runners.__all__)
        self.platforms = sorted(platforms.__all__)

        GObject.add_emission_hook(RunnersDialog, "runner-installed", self.update)

        # TODO: This should be in a more logical location
        icon_theme = Gtk.IconTheme.get_default()
        local_theme_path = os.path.join(datapath.get(), 'icons')
        if local_theme_path not in icon_theme.get_search_path():
            icon_theme.prepend_search_path(local_theme_path)

        all_row = SidebarRow(None, 'runner', 'All', None)
        self.add(all_row)
        self.select_row(all_row)
        for runner in self.runners:
            icon = Gtk.Image.new_from_icon_name(runner.lower().replace(' ', '') + '-symbolic',
                                                Gtk.IconSize.MENU)
            name = runners.import_runner(runner).human_name
            self.add(SidebarRow(runner, 'runner', name, icon))

        self.add(SidebarRow(None, 'platform', 'All', None))
        for platform in self.platforms:
            icon = Gtk.Image.new_from_icon_name(platform.lower().replace(' ', '') + '-platform-symbolic',
                                                Gtk.IconSize.MENU)
            self.add(SidebarRow(platform, 'platform', platform, icon))

        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.update()
        self.show_all()

    def _filter_func(self, row):
        if row is None:
            return True
        elif row.type == 'runner':
            if row.id is None:
                return True  # 'All'
            return row.id in self.installed_runners
        else:
            if len(self.active_platforms) <= 1:
                return False  # Hide useless filter
            elif row.id is None:  # 'All'
                return True
            return row.id in self.active_platforms

    def _header_func(self, row, before):
        if row.get_header():
            return

        if not before:
            row.set_header(SidebarHeader('Runners'))
        elif before.type == 'runner' and row.type == 'platform':
            row.set_header(SidebarHeader('Platforms'))

    def update(self, *args):
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.active_platforms = pga.get_used_platforms()
        self.invalidate_filter()
