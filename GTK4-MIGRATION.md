# GTK 4 Migration Notes

This document tracks practical notes for the GTK 3 to GTK 4 migration on the `dj/gtk4` branch.

## PyGObject Type Stubs

The `PyGObject-stubs` package ships stubs for both GTK 3 and GTK 4, selected at install time.
The `--no-cache-dir` flag is required to force a rebuild when switching versions.

**Install GTK 4 stubs** (for the `dj/gtk4` branch):

```bash
pip install PyGObject-stubs --no-cache-dir --force-reinstall --config-settings=config=Gtk4,Gdk4
```

**Install GTK 3 stubs** (for `master`):

```bash
pip install PyGObject-stubs --no-cache-dir --force-reinstall --config-settings=config=Gtk3,Gdk3
```

After switching stubs, reset the mypy baseline:

```bash
make mypy-reset-baseline
```

## Removed Classes

| GTK 3 | GTK 4 | Notes |
|---|---|---|
| `Gtk.Container` | `Gtk.Widget` | All container methods moved to `Gtk.Widget` |
| `Gtk.RadioButton` | `Gtk.CheckButton` + `set_group()` | Create with `Gtk.CheckButton()`, then call `set_group(other)` to link |

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

## GnomeDesktop / Display API

GnomeDesktop 3.0 (`gi.require_version('GnomeDesktop', '3.0')`) requires GTK 3 and cannot
be loaded alongside GTK 4. The `MutterDisplayManager` and `GnomeDesktopDisplayManager`
classes are unavailable; display resolution queries fall through to xrandr parsing via
`LegacyDisplayManager` in `lutris/util/graphics/xrandr.py`.

## Changes Made

Summary of files changed during the migration (most recent first):

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
