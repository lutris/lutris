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

## CSS Changes

- `Gtk.TextView` no longer has a `> text` child CSS node. Selectors like `.lutris-logview > text`
  must become `.lutris-logview` directly.
- `selection` is still a valid sub-selector but is no longer nested under `> text`.

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

## UI File Changes

- `<requires lib="gtk+" version="3.x"/>` becomes `<requires lib="gtk" version="4.0"/>`
- Remove `<packing>` elements, `border-width`, `window_position`, `show-close-button`
- Remove `<property name="visible">True</property>` (visible by default)
- `GtkSearchEntry` has a built-in search icon; remove `primary-icon-*` properties

## Label Alignment

GTK 4's `Gtk.Label` with `set_size_request()` needs explicit `xalign=0` to left-align text
within the allocated width. In GTK 3 this was handled implicitly by `halign=START` shrinking
the widget, but in GTK 4 the text centers within the requested size.
