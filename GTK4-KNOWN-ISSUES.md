# GTK 4 Port — Known Issues

This document describes behaviour that differs in the GTK 4 build of
Lutris from the previous GTK 3 release. A few features had no direct
GTK 4 equivalent and have been dropped, and a few defects remain that
we have not been able to fully resolve.

## Features Removed

### System tray icon

GTK 4 ships no replacement for `Gtk.StatusIcon`, and the
libappindicator / libayatana-appindicator family of libraries that took
over tray duties on Linux desktops still depend on GTK 3. There is no
AppIndicator 4 release. The tray icon — including the "minimize to
tray", quick-launch, and quit-from-tray affordances — is therefore
unavailable.

The closest replacements:

- Minimize the window; most desktop environments will park it on the
  taskbar.
- Close the window to exit the process and re-launch from your menu /
  dock when you need it.

### Installer-completion taskbar flash

When an install finished, the GTK 3 build flagged the installer window
for attention via `Gtk.Window.set_urgency_hint(True)`, which prompted
most taskbars and panels to flash. The hint was an X11 protocol concept;
Wayland never adopted an equivalent, and GTK 4 dropped the API. You
will need to watch the installer dialog or check back on it manually.

### gnome-desktop3 display detection

`gnome-desktop3` was the GNOME library Lutris used in the GTK 3 build to
query display modes and EDID-preferred resolutions. It requires GTK 3
and cannot load alongside GTK 4, so the GTK 4 build always falls through
to `xrandr` parsing for display information.

In practice this matches what KDE and other non-GNOME desktops always
did with the GTK 3 build. The xrandr binary therefore becomes a hard
runtime requirement; distributions package it as `x11-xserver-utils`
(Debian/Ubuntu) or `xrandr` (Fedora, openSUSE, Arch). Without it the
resolution dropdown collapses to a single default entry.

## Known Defects

### Some windows don't reliably take focus when re-raised on Wayland

When a dialog is already open and you trigger an action that re-opens
it, Wayland compositors (notably Mutter) sometimes refuse to give the
re-raised window keyboard focus. The window comes visually to the
front, but typing keeps going to whatever window had focus before. The
title bar usually looks dimmed when this happens.

We've added a 1-millisecond defer before re-raising, which fixes most
cases, but two situations remain:

- The **Configure** dialog re-opened from the game's right-click context
  menu still sometimes fails to take focus. Whether it works appears to
  depend on the vertical position of the mouse pointer at click time,
  which strongly suggests a heuristic inside Mutter that we cannot
  influence from the application.
- The **Preferences** dialog occasionally refuses to come to the front
  for a few seconds when re-opened, hinting at a separate rate-limit
  heuristic in the compositor.

Workaround: click the dialog's title bar once, or click the existing
window via the taskbar, to give it focus.

### Editable dropdowns now have a "Custom" choice

In a few places — such as the gamescope resolutions, the Wine virtual
desktop size and the DXVK versions — the GTK 3 build used an editable
combobox: a dropdown menu that also let you type a custom value if none
of the suggestions fit. GTK 4 dropped that widget entirely, and there
is no built-in replacement.

Instead, these dropdowns end with a **Custom** choice. Selecting it
shows a text entry beside the dropdown, where you can type any value;
the entry is hidden while one of the regular choices is selected. A
custom value you have saved is listed in the dropdown as a choice of
its own the next time you open the dialog.

A GTK 4 dropdown cannot be left with nothing selected, so where a
setting has no value the dropdown shows a named choice for that:
**Auto** for the resolutions where gamescope or Lutris picks the size,
and **None** elsewhere.

This takes an extra click compared to the GTK 3 version when entering
a custom value. We will revisit it if a suitable combined widget
appears in a future GTK release.
