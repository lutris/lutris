from gi.repository import Gdk, Gio, Gtk


def update_action_widget_visibility(widgets, visible_predicate):
    """This sets the visibility on a set of widgets, like menu items. You provide a function
    that indicates if an item is visible, or None for separators that are visible based on
    their neighbors. Returns the count of visible widgets that are not separators."""
    visible_count = 0
    previous_visible_widget = None
    for w in widgets:
        visible = visible_predicate(w)

        if visible:
            visible_count = visible_count + 1

        if visible is None:
            if previous_visible_widget is None:
                visible = False
            else:
                visible = visible_predicate(previous_visible_widget) is not None

        w.set_visible(visible)
        if visible:
            previous_visible_widget = w

    if previous_visible_widget and visible_predicate(previous_visible_widget) is None:
        previous_visible_widget.set_visible(False)
    return visible_count


class ContextualMenu:
    """Context menu using Gtk.PopoverMenu with Gio.Menu model for GTK4 compatibility."""

    def __init__(self, main_entries):
        self.main_entries = main_entries
        self._action_group = Gio.SimpleActionGroup()
        self._actions = {}

    def popup_at(self, widget, x, y, game_actions):
        """Show the context menu as a popover attached to widget at (x, y)."""
        displayed = game_actions.get_displayed_entries()

        menu = Gio.Menu()
        section = Gio.Menu()
        visible_count = 0

        for name, label, callback in self.main_entries:
            if label == "-":
                if section.get_n_items() > 0:
                    menu.append_section(None, section)
                    section = Gio.Menu()
                continue

            is_visible = displayed.get(name, True)
            if not is_visible:
                continue

            action_name = name.replace("-", "_")
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", lambda _action, _param, cb=callback: cb(None))
            self._action_group.add_action(action)
            self._actions[action_name] = action

            menu_item = Gio.MenuItem.new(label, "context." + action_name)
            section.append_item(menu_item)
            visible_count += 1

        if section.get_n_items() > 0:
            menu.append_section(None, section)

        if visible_count > 0:
            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.insert_action_group("context", self._action_group)
            popover.set_parent(widget)
            rect = Gdk.Rectangle()
            rect.x = int(x)
            rect.y = int(y)
            rect.width = 1
            rect.height = 1
            popover.set_pointing_to(rect)
            popover.set_has_arrow(False)
            popover.popup()
