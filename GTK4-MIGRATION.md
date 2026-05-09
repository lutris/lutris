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

For `get_root()` used as a dialog parent, narrow with `cast(Gtk.Widget, root)` before
passing to functions expecting `Widget` — every `Gtk.Root` implementation is also a
`Gtk.Widget` at runtime, so the cast is safe and reads more clearly than an
`isinstance` runtime check that always passes.

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

## Re-raising Already-Open Windows on Wayland

`Gtk.Window.present()` on an already-open window often fails to take
focus on Wayland/Mutter when called synchronously from the event
handler that triggered us. Mutter raises the window's z-order
(stacking) but refuses to give it keyboard focus — the dialog stays
visible but with a dimmed title bar, and typing keeps going to whatever
window had focus before. This is Mutter's focus-stealing prevention
acting on a `present()` call it doesn't believe is user-initiated.

We don't fully understand the heuristic. A plausible-but-incomplete
sketch: GTK forwards an `xdg-activation` token to Mutter when calling
`present()`; the token is delivered to the client over the Wayland
socket *after* the input event itself, so calling `present()`
synchronously runs without one. The GLib main loop only reads from the
socket when it `poll()`s, and `idle_add()` / `timeout_add(0, …)` both
dispatch without yielding to `poll()`. `timeout_add(1, …)` does — for
that millisecond — so the deferred callback runs after the token has
arrived.

The deferral helps measurably:

```python
GLib.timeout_add(1, lambda: bool(existing.present()))
```

What we've observed empirically:

- Synchronous, `idle_add`, `timeout_add(0)`: typically fail.
- `timeout_add(1)`: typically works.
- `time.sleep(0.001)` on the main thread: fails (blocks without
  polling).
- Async-via-thread (`AsyncCall`, `BusyAsyncCall`): works — and this is
  what disguised the bug for a long time, because the install path goes
  through `BusyAsyncCall` and worked, while the configure path was
  synchronous.

The pure "token in flight" theory doesn't explain everything though:

- Some entry points re-raise fine *without* any deferral at all (the
  toolbar `[+]` button being one).
- Configure from the right-click context menu *still* doesn't reliably
  reactivate even with the 1ms deferral, and the result depends on the
  vertical position of the mouse pointer at click time — top half of
  the screen tends to succeed, bottom half tends to fail. Proximity
  between the click and the dialog isn't the variable; it really seems
  to be raw screen geometry. There's no obvious GTK-side hook for
  whatever Mutter is computing here.
- The Preferences dialog raises most of the time but occasionally
  refuses for a few seconds, hinting at a separate rate-limit
  heuristic.

Earlier dead-ends: `Gdk.Toplevel.focus(0)`,
`present_with_time(GLib.get_monotonic_time() // 1000)`, re-calling
`set_transient_for()`, rebuilding the context menu without GAction.
None of those, on their own, helped.

Net: the 1ms deferral is committed as a cheap improvement that is
*usually* sufficient. The remaining gaps look like compositor-level
heuristics outside our reach without dropping below GTK to raw
`xdg-activation` protocol.

## Window Urgency Hint Removed

`Gtk.Window.set_urgency_hint()` was removed in GTK 4 with no direct replacement —
the X11 urgency hint (used to flash the taskbar entry to draw attention to a
window when a long-running operation finishes) has no Wayland equivalent and was
dropped wholesale. The closest modern analog is a freedesktop notification via
`Gio.Notification`, but that's a different UX (a popup, not a taskbar flash).

The installer window previously called `set_urgency_hint(True)` when an install
finished and cleared it on `focus-in-event`. Both signal and method are gone in
GTK 4; the behavior is dropped rather than reimplemented.

## Gdk.Keymap Removed

`Gdk.Keymap` is gone in GTK 4 — there's no API to query *live* modifier
state outside of an active event. `lutris/gui/dialogs/delegates.py`
previously used `Gdk.Keymap.get_default().get_modifier_state()` to detect a
held Shift key when launching a game, forcing the launch-config picker to
appear even when the user had a saved preferred config.

The closest GTK 4 equivalent is the modifier state attached to each input
device, which reflects whatever modifiers were held at that device's most
recent event:

```python
keyboard = Gdk.Display.get_default().get_default_seat().get_keyboard()
shift_held = bool(keyboard.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK)
```

This is "best-effort" rather than truly live — if the user releases Shift
between the click and the GAction handler firing, the state is stale —
but the window between those events is small enough in practice that the
shift-to-force-picker affordance still works as intended.

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

## Gtk.EntryCompletion

`Gtk.EntryCompletion` is deprecated in GTK 4 but still ships and still
works. Its intended replacement, `Gtk.SuggestionEntry`, has not yet
landed — it is slated for GTK 5. Until then, widgets that need an
autocomplete dropdown under a `Gtk.Entry` (we have one,
`SearchableEntrybox`) keep using `Gtk.EntryCompletion` as-is.

A hand-rolled replacement was attempted (non-autohiding `Gtk.Popover`
with a `Gtk.FilterListModel`-backed `Gtk.ListView`); it works, but the
focus dance required to keep typing alive while the popover is visible
isn't worth carrying for the duration of the GTK 4 cycle. When
`Gtk.SuggestionEntry` lands, swap `SearchableEntrybox` over to it.

## Factory-Item Snapshot Caching

`Gtk.Widget.queue_draw()` in GTK 4 invalidates a single widget's snapshot,
not its descendants — each widget's snapshot is cached independently.
For `Gtk.GridView` / `Gtk.ColumnView` cells (created by a
`Gtk.SignalListItemFactory`), this means `queue_draw()` on the **view**
won't re-snapshot the factory-created children. Refreshes that need to
run inside the cell's `do_snapshot` (e.g. reloading a texture against
new media) have to invalidate each cell widget directly.

Two patterns we use:

- **View walks its bound items.** Where the view tracks bound widgets
  in a set (`_bound_covers`), an event handler can iterate and call
  `queue_draw()` on each. Used for the `show_badges` setter, which also
  has to push fresh data into each cell.
- **Each cell registers itself.** Where the relevant lifecycle is per-
  cell rather than per-event, the cell connects to `realize` and
  `unrealize` to register / unregister a `NotificationSource`
  subscription. That keeps the notification source from holding strong
  references to dead pool widgets. `GameCoverWidget` does this for both
  `MEDIA_CACHE_INVALIDATED` (texture reload) and `MISSING_GAMES.updated`
  (missing-badge repaint), so updated media and changed install status
  both repaint in place rather than waiting for a scroll-induced rebind.

## Class-level Image Caches and the Factory Pool

The GTK 3 cell renderer used a single shared image cache because one
`CellRenderer` instance painted every cell. In GTK 4, each cell is its
own widget, so an instinct to keep a class-level image cache for cross-
widget sharing carries over — but `Gtk.GridView` / `Gtk.ColumnView` pool
their factory widgets to roughly the visible-cell count, and there's
exactly one game per cell. Empirical measurement (per-widget miss vs.
class-level hit, instrumented in `_get_cached_texture_by_path`) showed
the cross-widget hit rate was effectively zero in real scroll patterns:
the pool already covers the same ground a class-level cache would.

So `GameCoverWidget` keeps the texture per-widget — a single
`self._texture` refreshed when its `(path, size, scale)` key changes —
and the only class-level cache left is the badge-icon dict, which has
real reuse (every cover sharing a platform draws the same badge).

`MEDIA_CACHE_INVALIDATED` invalidates per-widget textures via the
realize/unrealize registration described above; the badge dict is
cleared directly from a module-level handler on the same notification.
There is no longer a generation-number indirection or a two-generation
old/new cycle.

## GridView Thumb-Drag Flicker (Unresolved)

**Symptom**: In the games grid, holding the scrollbar thumb still — not moving
the mouse, just keeping the button held — causes a visible flicker at the
viewport edges, with one row of cells redrawing at ~15–22 Hz. Releasing the
mouse settles it. Observed on KDE/Wayland with fractional scaling.

**Investigation findings**:

- The vertical adjustment's `value` oscillates by ±10–14 units at ~100 Hz
  while the thumb is held. At the scrollbar track's ~21 units/pixel, that's
  sub-pixel mouse jitter getting amplified into ~14 pixels of viewport shift
  — plenty to push cells across visibility thresholds.
- During the flicker, `GridView` emits 1 500–1 700 `bind`/`unbind` factory
  calls per second, with the bound-position set spanning the *entire* model
  range (0 to 274 for a 275-game library), not just the viewport-adjacent
  cells. That looks like a full layout invalidation cycle, not a scroll-shift
  rebinding.
- The adjustment's `upper` (content height) also oscillated by 2–6 pixels
  until overlay scrolling was disabled. Remaining oscillation may be
  fractional-scaling rounding on KDE/Wayland.
- Only five cells (one row) snapshot 15× per second during the flicker, which
  is what the eye sees.

**What measurably reduced frequency** (changes were subsequently reverted
pending a real fix — record here so the next attempt starts informed):

- `Gtk.ScrolledWindow.set_overlay_scrolling(False)` — stabilised `upper`.
- `Gtk.ScrolledWindow.set_kinetic_scrolling(False)` — removed momentum
  feedback.
- Pinning the per-cell `Gtk.Box` to a fixed height via `set_size_request` in
  the factory's `setup` — broke a feedback loop where labels with short
  names measured at 1 line and long names at 2, so row height depended on
  which cells GridView happened to sample, which depended on scroll
  position. Pinning the box breaks that loop.
- `GridView.set_focusable(False) / set_can_focus(False)` — defensive; no
  direct evidence it helped.

Together these reduced flicker from "constant while dragging" to "rare and
hard to reproduce", but did not eliminate it.

**What didn't help**:

- `GTK_OVERLAY_SCROLLING=0` env var — ignored; overlay scrolling must be
  disabled programmatically on each `Gtk.ScrolledWindow`.
- Snapping `vadjustment.value` to multiples of 16 units in a
  `value-changed` handler. Our handler is attached after GridView's
  internal handler, so GridView reads and reacts to the raw value first,
  then the snap sets a new value and re-emits — GridView sees *both*
  values and queues two layouts. Adds churn, not reduces.
- Removing diagnostic logging from the factory `bind`/`unbind` callbacks
  and the `do_snapshot` of `GameCoverWidget`: while those probes were
  attached, flicker was rare; after removal it became easy again. That
  strongly implies the per-event work on the Python side was nudging GTK's
  event timing enough to coalesce updates — not a principled fix, but a
  data point about how close we are to a rate where GridView keeps up.

**Theories for the root cause**:

- `Gtk.GridView` invalidates and re-binds across its whole widget pool in
  response to small `vadjustment` changes (or internal layout passes
  triggered by them), rather than rebinding only cells that cross the
  viewport boundary. The bind-position range covering the full model
  during the flicker is consistent with this.
- Fractional scaling + sub-pixel mouse motion produces sub-pixel changes
  that round differently across frames, forcing relayout even when the
  logical viewport shouldn't have moved.
- There is no hook to debounce `vadjustment.value-changed` *before*
  GridView's internal handler, because that handler is connected from C
  at construction, ahead of anything we can connect from Python.

**Possible next steps**:

- Subclass or wrap `Gtk.ScrolledWindow` and replace the `vadjustment` with
  one that coalesces rapid changes into a single `value-changed` dispatch
  per tick. The trick is keeping the scrollbar thumb responsive — the
  coalesced value has to be visible to the scrollbar's own handler
  immediately, just not to GridView.
- Hook into the scrollbar's drag gesture directly (`Gtk.Scrollbar`'s
  internal gesture is not public, so this likely requires a custom
  scrollbar) and round the resulting value to row-aligned steps during
  the drag.
- File upstream against `Gtk.GridView` with a reduced reproducer; the
  full-model rebind on sub-row adjustments looks like a bug independent
  of our code.

**Relevant files**: `lutris/gui/views/grid.py`, `lutris/gui/lutriswindow.py`
(ScrolledWindow construction), `lutris/gui/widgets/game_cover.py`
(per-cell snapshot cost).

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
