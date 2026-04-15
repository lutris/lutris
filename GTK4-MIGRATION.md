# GTK 4 Migration Notes

This document tracks practical notes for the GTK 3 to GTK 4 migration on the `dj/gtk4` branch.

## PyGObject Type Stubs

The `PyGObject-stubs` package ships stubs for both GTK 3 and GTK 4, selected at install time
via `--config-settings=config=...`. Only one version can be installed at a time, so switching
branches between `master` and `dj/gtk4` requires reinstalling the stubs to match.

**Symptom of a mismatch**: `make mypy` floods with errors about GTK 4 methods that "don't exist" —
`add_controller`, `set_child`, `Gtk.DropTarget`, `add_css_class`, etc. If you see ~180 new
`attr-defined` errors after switching to `dj/gtk4`, the stubs are still the GTK 3 version.

**Install GTK 4 stubs** (for the `dj/gtk4` branch — this is what `make dev` does):

```bash
pip install 'pygobject-stubs>=2.17.0' --no-cache-dir --force-reinstall \
    --config-settings=config=Gtk4,Gdk4,Soup2
```

**Install GTK 3 stubs** (for `master`):

```bash
pip install 'pygobject-stubs>=2.17.0' --no-cache-dir --force-reinstall \
    --config-settings=config=Gtk3,Gdk3,Soup2
```

The `--no-cache-dir` flag is required to force pip to rebuild the wheel with the new config
rather than reusing a cached build. After switching stubs, also clear the mypy cache
(`rm -rf .mypy_cache`) since mypy caches the old type info.

If switching stubs legitimately introduces new errors that won't be fixed immediately, reset
the mypy baseline:

```bash
make mypy-reset-baseline
```

## Removed Classes

| GTK 3 | GTK 4 | Notes |
|---|---|---|
| `Gtk.Container` | `Gtk.Widget` | All container methods moved to `Gtk.Widget` |
| `Gtk.RadioButton` | `Gtk.CheckButton` + `set_group()` | Create with `Gtk.CheckButton()`, then call `set_group(other)` to link |
| `Gtk.ComboBox` | `Gtk.DropDown` / `KeyValueDropDown` | See section below |

## Removed APIs (common patterns)

| GTK 3 | GTK 4 |
|---|---|
| `container.add(widget)` | `box.append(widget)` / `parent.set_child(widget)` |
| `pack_start(child, expand, fill, pad)` | `append(child)` + `child.set_hexpand(True)` |
| `show_all()` | Remove (widgets visible by default) |
| `get_style_context().add_class(name)` | `add_css_class(name)` |
| `set_border_width(n)` | `set_margin_top/bottom/start/end(n)` |
| `get_toplevel()` | `get_root()` |
| `builder.connect_signals(self)` | Connect signals manually |
| `Gtk.Image.new_from_icon_name(name, size)` | `Gtk.Image.new_from_icon_name(name)` + `set_icon_size()` |
| `GdkPixbuf.Pixbuf.new_from_file_at_size()` | `Gdk.Texture.new_from_filename()` + `Gtk.Image.new_from_paintable()` |
| `override_font()` | `Gtk.CssProvider` with `font-size` property |
| `button-press-event` signal | `Gtk.GestureClick` controller |
| `key-press-event` signal | `Gtk.EventControllerKey` controller |
| `delete-event` signal | `close-request` signal |
| `Gtk.Menu` | `Gtk.PopoverMenu` + `Gio.Menu` |
| Stock labels (`gtk-save`) | Named icons (`document-save-symbolic`) |
| `Gtk.Dialog(parent=window)` | `Gtk.Dialog()` + `set_transient_for(window)` |
| `HeaderBar.set_subtitle()` | `WindowTitle` widget (see below) |

## HeaderBar Subtitle

`Gtk.HeaderBar.set_subtitle()` was removed in GTK 4. The libadwaita replacement
is `Adw.WindowTitle`, but since Lutris does not use libadwaita, we provide our own
`WindowTitle` widget in `lutris/gui/widgets/common.py`:

```python
from lutris.gui.widgets.common import WindowTitle

title_widget = WindowTitle(title="Remove Games", subtitle="Uninstall 3 games")
header_bar.set_title_widget(title_widget)

# Update subtitle later:
title_widget.set_subtitle("Uninstall 2 games")
```

Uses the built-in `title` and `subtitle` CSS classes for correct header bar styling.

## ComboBox to DropDown

`Gtk.ComboBox` is deprecated in GTK 4. It still works but relies on the old
`Gtk.ListStore` + `Gtk.CellRendererText` pattern which is also deprecated.
The replacement is `Gtk.DropDown`, which uses `Gtk.StringList` or `Gio.ListStore`.

### KeyValueDropDown helper

Most Lutris ComboBoxes used a `ListStore(str, str)` with a display column and an ID column.
`Gtk.DropDown` has no built-in concept of an ID column — it works with position indices only.

`KeyValueDropDown` (in `lutris/gui/widgets/common.py`) wraps `Gtk.DropDown` with a
`Gtk.StringList` and a parallel list of IDs, providing a familiar interface:

```python
from lutris.gui.widgets.common import KeyValueDropDown

dropdown = KeyValueDropDown()
dropdown.append("wine", "Wine (Wine Is Not an Emulator)")
dropdown.append("proton", "Proton")
dropdown.set_active_id("wine")

selected_id = dropdown.get_active_id()     # "wine"
selected_label = dropdown.get_active_label()  # "Wine (Wine Is Not an Emulator)"
dropdown.connect("changed", on_changed)    # emitted on selection change
dropdown.clear()                           # remove all items
```

Use `set_size_request(240, -1)` if the dropdown would otherwise be too narrow.

### choice_with_entry (editable dropdowns)

`Gtk.DropDown` has no editable entry mode — there is no equivalent of
`Gtk.ComboBox.new_with_model_and_entry()`. GTK 4 does not provide a built-in
widget that combines a dropdown with free-text entry.

The workaround is a `Gtk.Box` containing a `KeyValueDropDown` and a `Gtk.Entry`.
Selecting from the dropdown populates the entry; the entry also accepts free text.
This is implemented in `widget_generator.py`'s `_generate_choice()` method when
`has_entry=True`.

## Nullability Changes

Several APIs that returned non-null in GTK 3 stubs now return nullable types in GTK 4 stubs.
These need `None` guards:

- `Gdk.Display.get_default()` returns `Display | None`
- `Gdk.Display.get_monitors().get_item(n)` returns `Monitor | None`
- `Gtk.Widget.get_root()` returns `Root | None` (and `Root` is not a `Widget` subtype in stubs)
- `Gtk.EventController.get_widget()` returns `Widget | None`
- `Gtk.ComboBox.get_model()` returns `TreeModel | None`
- `Gtk.IconTheme.get_search_path()` returns `list[str] | None`

For `get_root()` used as a dialog parent, narrow with `isinstance(root, Gtk.Widget)` before
passing to functions expecting `Widget`.

## Mixin Classes and Type Checking

Mixin classes that assume `Gtk.Widget` methods (like `get_root()`) need type stubs for mypy.
Use `TYPE_CHECKING` to declare the expected interface without affecting the runtime MRO:

```python
from typing import TYPE_CHECKING

class MyMixin:
    if TYPE_CHECKING:
        def get_root(self) -> Gtk.Root | None: ...
```

## CSS Changes

- `Gtk.TextView` no longer has a `> text` child CSS node. Selectors like `.lutris-logview > text`
  must become `.lutris-logview` directly.
- `selection` is still a valid sub-selector but is no longer nested under `> text`.

## UI File Changes

- `<requires lib="gtk+" version="3.x"/>` becomes `<requires lib="gtk" version="4.0"/>`
- Remove `<packing>` elements, `border-width`, `window_position`, `show-close-button`
- Remove `<property name="visible">True</property>` (visible by default)
- `GtkSearchEntry` has a built-in search icon; remove `primary-icon-*` properties

## Label Alignment

GTK 4's `Gtk.Label` with `set_size_request()` needs explicit `xalign=0` to left-align text
within the allocated width. In GTK 3 this was handled implicitly by `halign=START` shrinking
the widget, but in GTK 4 the text centers within the requested size.

## Widget Spacing

GTK 4 renders some widgets with more internal padding than GTK 3 (notably `Gtk.ComboBox`
and grid rows). Margins and spacing values that looked fine in GTK 3 may feel too loose.
The search filters panel needed margins reduced from 20px to 12px, box spacing from 10px
to 4px, and grid row spacing from 6px to 2px to look comparable.

## PopoverMenu Section Separators

`GtkPopoverMenu` built from a `Gio.Menu` with `append_section()` inserts its section
separators (and the 10px top-margin fallback used when a separator is suppressed) from a
`G_PRIORITY_DEFAULT` idle callback in `gtk_menu_section_box_schedule_separator_sync()`. If
you call `popover.popup()` synchronously right after `new_from_model()`, measurement happens
*before* that idle runs, so the natural size undercounts all the separator overhead. The
compositor sizes the xdg-popup at the undercounted value, the separators then appear, and
the contents overflow into a scrolled view.

Workaround: defer `popover.popup()` via `GLib.idle_add()`. Python's default priority is
`G_PRIORITY_DEFAULT_IDLE` (200), which runs after GTK's `G_PRIORITY_DEFAULT` (0) separator
sync, so measure happens with the separators in place. See
`lutris/gui/widgets/contextual_menu.py`.

A cleaner long-term approach is to build the menu model once at construction time and only
call `popup()` on click, which gives GTK time to run the separator-sync idle between
creation and presentation.

## GnomeDesktop / Display API

GnomeDesktop 3.0 (`gi.require_version('GnomeDesktop', '3.0')`) requires GTK 3 and cannot
be loaded alongside GTK 4. The `MutterDisplayManager` and `GnomeDesktopDisplayManager`
classes are unavailable; display resolution queries fall through to xrandr parsing via
`LegacyDisplayManager` in `lutris/util/graphics/xrandr.py`.

## SearchEntry Return Key Handling

`Gtk.SearchEntry` consumes the Return key internally and emits `activate` rather
than forwarding it to `key-press-event`. In GTK 4 there is no `key-press-event`
signal at all — use `Gtk.EventControllerKey` for modifier combinations, but
connect the plain `activate` signal for bare Return. Example in
`lutris/gui/dialogs/log.py`: `activate` advances to the next search match;
`EventControllerKey` handles Shift+Return for the previous match.

## GAction and Focus-Stealing Prevention

On Wayland (tested on GNOME/Mutter), calling `Gtk.Window.present()` on an
already-open window from a handler invoked via `GAction` (menu items with
`action-name`, keyboard shortcuts routed through `Gtk.Application` actions) does
not raise the window — Mutter treats it as focus-stealing and either does
nothing (if the window is frontmost) or shows a "Ready" notification.

The same `present()` call from a plain `Gtk.Button.clicked` handler works
correctly. The difference is that `GAction` activation is deliberately
decoupled from its triggering event, so GTK has no xdg-activation token to
forward to the compositor when `present()` runs.

Tried and didn't help: `Gdk.Toplevel.focus(0)`,
`present_with_time(GLib.get_monotonic_time() // 1000)`, re-calling
`set_transient_for()`. The token truly isn't available at the callsite.

Fixing this properly requires capturing the triggering event's timestamp
before the `GAction` dispatches (e.g. via a `Gtk.GestureClick` on the menu
item) and threading it to `present_with_time()`. Not yet done — affects only
the re-raise path for already-open dialogs.

## Window Urgency Hint Removed

`Gtk.Window.set_urgency_hint()` was removed in GTK 4 with no direct replacement —
the X11 urgency hint (used to flash the taskbar entry to draw attention to a
window when a long-running operation finishes) has no Wayland equivalent and was
dropped wholesale. The closest modern analog is a freedesktop notification via
`Gio.Notification`, but that's a different UX (a popup, not a taskbar flash).

The installer window previously called `set_urgency_hint(True)` when an install
finished and cleared it on `focus-in-event`. Both signal and method are gone in
GTK 4; the behavior is dropped rather than reimplemented.

## Tracking Application Windows

`Gtk.Application` already tracks its attached windows — iterate with
`self.get_windows()` instead of maintaining a parallel dict. Attach a key
attribute to each window at creation time, then look it up with a linear scan:

```python
def _find_window(self, window_class, window_key):
    for existing in self.get_windows():
        if isinstance(existing, window_class) and getattr(existing, "_app_window_key", None) == window_key:
            return existing
    return None
```

This avoids the GTK 3 pattern of connecting to `destroy` on every window to
remove stale dict entries, which is fragile under GTK 4 where windows
participate in `Gtk.Application`'s lifecycle automatically.

## Changes Made

Summary of files changed during the migration (most recent first):

### Application window tracking
- `lutris/gui/application.py` — Removed `app_windows` dict; `show_window()` now scans `get_windows()`
- `lutris/gui/dialogs/__init__.py` — Removed `ModelessDialog._remove_from_app_windows` hack
- `lutris/gui/dialogs/uninstall_dialog.py` — Removed `_on_close_request`/`destroy` override

### Log window search navigation
- `lutris/gui/dialogs/log.py` — `activate` signal for Return, `EventControllerKey` for Shift+Return

### HeaderBar subtitle restoration
- `lutris/gui/widgets/common.py` — Added `WindowTitle` widget (replaces `Adw.WindowTitle`)
- `lutris/gui/config/edit_game_categories.py` — Subtitle showing game count
- `lutris/gui/dialogs/uninstall_dialog.py` — Subtitle describing removal action

### ComboBox to DropDown conversion
- `lutris/gui/widgets/common.py` — Added `KeyValueDropDown` helper widget
- `lutris/gui/config/edit_saved_search.py` — Search filter dropdowns
- `lutris/gui/config/game_info_box.py`, `lutris/gui/config/game_common.py` — Runner selector
- `lutris/gui/addgameswindow.py` — Installer preset and locale dropdowns
- `lutris/gui/installerwindow.py` — Installer input menu
- `lutris/gui/installer/file_box.py` — File source provider dropdown
- `lutris/gui/config/widget_generator.py` — `choice` and `choice_with_entry` config options

### mypy type fixes (all files)
- `lutris/gui/config/widget_generator.py`, `lutris/gui/config/boxes.py` — `Gtk.Container` to `Gtk.Widget`
- `lutris/gui/config/updates_box.py` — `Gtk.RadioButton` to `Gtk.CheckButton`, `get_root()` guard
- `lutris/gui/dialogs/__init__.py` — `set_transient_for()` handles `Widget` parents via `get_root()`
- `lutris/gui/widgets/utils.py` — `Display.get_default()` null guards, `search_path` null guard
- `lutris/gui/widgets/sidebar.py` — `get_widget()` null guards
- `lutris/gui/widgets/download_progress_box.py` — `get_root()` type narrowing
- `lutris/gui/config/game_common.py` — `get_model()` null guard
- `lutris/gui/application.py` — `Display` null guard, `Dialog` parent kwarg
- `lutris/gui/views/base.py` — `TYPE_CHECKING` stub for `GameView.get_root()`
- `lutris/util/display.py` — `Monitor` null guard, fixed `Output` field names (`modes`/`current_mode` to `mode`)

### Search filters panel
- `lutris/gui/config/edit_saved_search.py` — Label `xalign=0`, reduced margins/spacing

### Log window
- `lutris/gui/dialogs/log.py` — Removed `connect_signals()`, added `window.present()`, zoom via CSS
- `share/lutris/ui/log-window.ui` — Removed invalid `primary-icon-*` props, `document-save-symbolic` icon
- `share/lutris/ui/lutris.css` — Fixed `.lutris-logview` CSS selectors for GTK 4 node structure

### Add Games dialog
- `lutris/gui/addgameswindow.py` — `GdkPixbuf` to `Gdk.Texture` for SVG icon loading
