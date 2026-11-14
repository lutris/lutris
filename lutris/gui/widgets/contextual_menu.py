from gi.repository import Gdk, GLib, Gtk


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
    """Context menu for games. This is built by hand, and is not a Gtk.PopoverMenu, because
    that closes before it activates an item. On Wayland a window can't be reliably focused
    from the item's callback unless the menu is still open. See reraise_window()."""

    def __init__(self, main_entries):
        self.main_entries = main_entries

    def popup_at(self, widget, x, y, game_actions):
        """Show the context menu as a popover attached to widget at (x, y)."""
        displayed = game_actions.get_displayed_entries()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover = Gtk.Popover(child=box, has_arrow=False)
        popover.add_css_class("menu")

        def on_clicked(_button, callback):
            # Close at idle, so the menu is open during the callback but does not
            # linger if that runs a main loop of its own for a modal dialog.
            GLib.idle_add(popover.popdown)
            callback(None)

        def track_selection(item):
            # The theme highlights the 'selected' menu item, not the hovered one; like
            # Gtk.PopoverMenu, we select the item under the pointer or focused by keyboard.
            def select(*_args):
                item.set_state_flags(Gtk.StateFlags.SELECTED, False)
                item.grab_focus()

            def unselect(*_args):
                item.unset_state_flags(Gtk.StateFlags.SELECTED)

            def on_state_flags_changed(_item, old_flags):
                # The first item gets the focus when the menu opens, but should not look
                # selected then; so we look for the visible focus that keyboard use gives.
                if item.get_state_flags() & ~old_flags & Gtk.StateFlags.FOCUS_VISIBLE:
                    select()

            motion = Gtk.EventControllerMotion()
            motion.connect("enter", select)
            motion.connect("leave", unselect)
            item.add_controller(motion)
            focus = Gtk.EventControllerFocus()
            focus.connect("leave", unselect)
            item.add_controller(focus)
            item.connect("state-flags-changed", on_state_flags_changed)

        visibility = {}
        for name, label, callback in self.main_entries:
            if label == "-":
                item = Gtk.Separator()
                visibility[item] = None
            else:
                # The 'modelbutton' CSS name gets us the theme's menu item style.
                item = Gtk.Button(css_name="modelbutton", child=Gtk.Label(label=label, xalign=0, use_underline=True))
                item.connect("clicked", on_clicked, callback)
                track_selection(item)
                visibility[item] = displayed.get(name, True)
            box.append(item)

        if update_action_widget_visibility(visibility, visibility.get) > 0:
            popover.set_parent(widget)
            popover.connect("closed", lambda p: GLib.idle_add(p.unparent))
            rect = Gdk.Rectangle()
            rect.x = int(x)
            rect.y = int(y)
            rect.width = 1
            rect.height = 1
            popover.set_pointing_to(rect)
            popover.popup()
