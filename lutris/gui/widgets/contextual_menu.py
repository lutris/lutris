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


def get_menu_popover(items, **popover_properties):
    """Returns a popover that looks like a Gtk.PopoverMenu, but contains the widgets given,
    which should come from get_menu_item().

    We do not use Gtk.PopoverMenu itself because that closes before it activates an item.
    On Wayland a window can't be reliably focused from the item's callback unless the menu
    is still open. See reraise_window()."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    for item in items:
        box.append(item)
    popover = Gtk.Popover(child=box, **popover_properties)
    popover.add_css_class("menu")
    return popover


def get_menu_item(label, callback=None):
    """Returns a button that looks and acts like an item of a Gtk.PopoverMenu, or a separator
    if the label is '-'. This is for use in get_menu_popover(). The callback is called with
    the button when it is clicked, and then the menu closes."""
    if label == "-":
        return Gtk.Separator()

    # The 'modelbutton' CSS name gets us the theme's menu item style. But the theme highlights
    # the 'selected' menu item, not the hovered one; so like Gtk.PopoverMenu, we select the
    # item under the pointer or focused by keyboard.
    item = Gtk.Button(css_name="modelbutton", child=Gtk.Label(label=label, xalign=0))

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

    def on_clicked(_item):
        # Close at idle, so the menu is open during the callback but does not
        # linger if that runs a main loop of its own for a modal dialog.
        popover = item.get_ancestor(Gtk.Popover)
        if popover:
            GLib.idle_add(popover.popdown)
        callback(item)

    motion = Gtk.EventControllerMotion()
    motion.connect("enter", select)
    motion.connect("leave", unselect)
    item.add_controller(motion)
    focus = Gtk.EventControllerFocus()
    focus.connect("leave", unselect)
    item.add_controller(focus)
    item.connect("state-flags-changed", on_state_flags_changed)
    if callback:
        item.connect("clicked", on_clicked)
    return item


class ContextualMenu:
    """Context menu for games."""

    def __init__(self, main_entries):
        self.main_entries = main_entries

    def popup_at(self, widget, x, y, game_actions):
        """Show the context menu as a popover attached to widget at (x, y)."""
        displayed = game_actions.get_displayed_entries()
        visibility = {}
        for name, label, callback in self.main_entries:
            visibility[get_menu_item(label, callback)] = None if label == "-" else displayed.get(name, True)

        if update_action_widget_visibility(visibility, visibility.get) > 0:
            popover = get_menu_popover(visibility, has_arrow=False)
            popover.set_parent(widget)
            popover.connect("closed", lambda p: GLib.idle_add(p.unparent))
            rect = Gdk.Rectangle()
            rect.x = int(x)
            rect.y = int(y)
            rect.width = 1
            rect.height = 1
            popover.set_pointing_to(rect)
            popover.popup()
