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


class SidebarTreeView(Gtk.TreeView):
    def __init__(self):
        super(SidebarTreeView, self).__init__()
        self.installed_runners = []
        self.active_platforms = []

        self.model = Gtk.TreeStore(str, str, GdkPixbuf.Pixbuf, str, str)
        self.model_filter = self.model.filter_new()
        self.model_filter.set_visible_func(self.filter_rule)
        self.set_model(self.model_filter)

        column = Gtk.TreeViewColumn("Runners")
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)

        # Type
        type_renderer = Gtk.CellRendererText()
        type_renderer.set_visible(False)
        column.pack_start(type_renderer, True)
        column.add_attribute(type_renderer, "text", TYPE)

        # Runner slug
        text_renderer = Gtk.CellRendererText()
        text_renderer.set_visible(False)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", SLUG)

        # Icon
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_renderer.set_property('width', 20)
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "pixbuf", ICON)

        # Label
        text_renderer2 = Gtk.CellRendererText()
        column.pack_start(text_renderer2, True)
        column.add_attribute(text_renderer2, "text", LABEL)

        # Gamecount
        text_renderer3 = Gtk.CellRendererText()
        text_renderer3.set_alignment(1.0, 0.5)
        column.pack_start(text_renderer3, True)
        column.add_attribute(text_renderer3, "text", GAMECOUNT)

        self.append_column(column)
        self.set_headers_visible(False)
        self.set_fixed_height_mode(True)

        self.get_selection().set_mode(Gtk.SelectionMode.BROWSE)

        # self.connect('button-press-event', self.popup_contextual_menu)
        GObject.add_emission_hook(RunnersDialog, "runner-installed", self.update)

        self.runners = sorted(runners.__all__)
        self.platforms = sorted(platforms.__all__)
        self.platform_node = None
        self.load_runners()
        self.load_platforms()
        self.update()
        self.expand_all()

    def load_runners(self):
        """Append runners to the model."""
        self.runner_node = self.model.append(None, ['runners', '', None, "All runners", None])
        for slug in self.runners:
            self.add_runner(slug)

    # def add_runner(self, slug):
    #     name = runners.import_runner(slug).human_name
    #     icon = get_runner_icon(slug, format='pixbuf', size=(16, 16))
    #     self.model.append(self.runner_node, ['runners', slug, icon, name, None])

    def load_platforms(self):
        """Update platforms in the model."""
        self.platform_node = self.model.append(None, ['platforms', '', None, "All platforms", None])
        for platform in self.platforms:
            self.add_platform(platform)

    def add_platform(self, name):
        self.model.append(self.platform_node, ['platforms', name, None, name, None])

    def get_selected_filter(self):
        """Return the selected runner's name."""
        selection = self.get_selection()
        if not selection:
            return None
        model, iter = selection.get_selected()
        if not iter:
            return None
        type = model.get_value(iter, TYPE)
        slug = model.get_value(iter, SLUG)
        return type, slug

    def filter_rule(self, model, iter, data):
        if not model[iter][0]:
            return False
        if (model[iter][0] == 'runners' or model[iter][0] == 'platforms') and model[iter][1] == '':
            return True
        return (model[iter][0] == 'runners' and model[iter][1] in self.installed_runners) or \
               (model[iter][0] == 'platforms' and model[iter][1] in self.active_platforms)

    def update(self, *args):
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.update_runners_game_count(pga.get_used_runners_game_count())
        self.active_platforms = pga.get_used_platforms()
        self.update_platforms_game_count(pga.get_used_platforms_game_count())
        self.model_filter.refilter()
        self.expand_all()
        # Return False here because this method is called with GLib.idle_add
        return False

    def update_runners_game_count(self, counts):
        runner_iter = self.model.iter_children(self.runner_node)
        self.update_iter_game_counts(runner_iter, counts)

    def update_platforms_game_count(self, counts):
        platform_iter = self.model.iter_children(self.platform_node)
        self.update_iter_game_counts(platform_iter, counts)

    def update_iter_game_counts(self, model_iter, counts):
        while model_iter is not None:
            slug = self.model.get_value(model_iter, SLUG)
            count = counts.get(slug, 0)
            count_display = "({0})".format(count)
            self.model.set_value(model_iter, GAMECOUNT, count_display)

            model_iter = self.model.iter_next(model_iter)

    # def popup_contextual_menu(self, view, event):
    #     if event.button != 3:
    #         return
    #     view.current_path = view.get_path_at_pos(event.x, event.y)
    #     if view.current_path:
    #         view.set_cursor(view.current_path[0])
    #         type, slug = self.get_selected_filter()
    #         if type != 'runners' or not slug or slug not in self.runners:
    #             return
    #         menu = ContextualMenu()
    #         menu.popup(event, slug, self.get_toplevel())

    #     self.add(self.box)

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
