from gi.repository import Gtk


def update_action_widget_visibility(widgets, visible_predicate):
    """This sets the visibility on a set of widgets, like menu items. You provide a function
    that indicates if an item is visible, or None for separators that are visible based on
    their neighbors."""
    previous_visible_widget = None
    for w in widgets:
        visible = visible_predicate(w)

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


class ContextualMenu(Gtk.Menu):
    def __init__(self, main_entries):
        super().__init__()
        self.main_entries = main_entries

    def add_menuitem(self, entry):
        """Add a menu item to the current menu

        Params:
            entry (tuple): tuple containing name, label and callback

        Returns:
            Gtk.MenuItem
        """
        name, label, callback = entry
        if label == "-":
            separator = Gtk.SeparatorMenuItem()
            self.append(separator)
            return separator

        action = Gtk.Action(name=name, label=label)
        action.connect("activate", callback)

        menu_item = action.create_menu_item()
        menu_item.action_id = name
        self.append(menu_item)
        return menu_item

    def get_runner_entries(self, game):
        if not game:
            return None

        runner = game.runner

        if not runner:
            return None

        return runner.context_menu_entries

    def popup(self, event, game_actions):
        for item in self.get_children():
            self.remove(item)

            for entry in self.main_entries:
                self.add_menuitem(entry)

        self.show_all()

            displayed = game_actions.get_displayed_entries()

            def is_visible(w):
                if isinstance(w, Gtk.SeparatorMenuItem):
                    return None

                return displayed.get(w.action_id, True)

            update_action_widget_visibility(self.get_children(), is_visible)

            super().popup_at_pointer(event)
