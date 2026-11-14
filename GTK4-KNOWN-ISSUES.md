# GTK 4 Port — Known Issues

This document describes behaviour that differs in the GTK 4 build of
Lutris from the previous GTK 3 release. A few features had no direct
GTK 4 equivalent and have been dropped, a few work differently, and a
defect remains that we have not been able to fully resolve.

## Features Removed

### System tray icon

GTK 4 ships no replacement for `Gtk.StatusIcon`, and the
libappindicator / libayatana-appindicator libraries that took over tray
duties on Linux desktops, and that Lutris used, depend on GTK 3. There
is no AppIndicator 4 release. A tray icon can be had without them, but
only by implementing the underlying D-Bus protocols ourselves, which we
have not done. The tray icon — including the "minimize to tray",
quick-launch, and quit-from-tray affordances — is therefore
unavailable.

The closest replacements:

- Minimize the window; most desktop environments will park it on the
  taskbar.
- Close the window to exit the process and re-launch from your menu /
  dock when you need it.

### gnome-desktop3 display detection

`gnome-desktop3` was a GNOME library Lutris could use in the GTK 3
build to query display modes and EDID-preferred resolutions. It
requires GTK 3 and cannot load alongside GTK 4.

On GNOME this changes nothing: Lutris asks Mutter for display
information over D-Bus, as before. On other desktops the GTK 4 build
always falls through to `xrandr` parsing, which is what the GTK 3 build
did there too unless `gnome-desktop3` happened to be installed.

The xrandr binary is therefore a hard runtime requirement outside
GNOME; distributions package it as `x11-xserver-utils` (Debian/Ubuntu)
or `xrandr` (Fedora, openSUSE, Arch). Without it the resolution
dropdown collapses to a single default entry.

## Behaviour Changes

### Installer-completion taskbar flash

When an install finished, the GTK 3 build flagged the installer window
for attention via `Gtk.Window.set_urgency_hint(True)`, which prompted
most taskbars and panels to flash. GTK 4 dropped that API.

The GTK 4 build asks the compositor to activate the installer window
instead, but only while no Lutris window has the focus. The compositor
will not hand the focus to an application in the background, and flags
the window for attention: GNOME shows a notification that the window
is ready, and other desktops typically flash the taskbar entry.

Two differences from GTK 3 remain:

- If you are working in another Lutris window when the install
  finishes, nothing happens; the GTK 3 build flashed the installer's
  taskbar entry then too.
- Mutter does not flag a window that is in full view, with nothing
  overlapping it.

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

## Known Defects

### Some windows don't take focus when re-raised from the main menu on Wayland

When a dialog is already open and you trigger an action that re-opens
it, Lutris asks the compositor to bring it forward and give it keyboard
focus. Mutter only agrees if the window you clicked in is still under
the mouse pointer. A menu closes as you click it, so what counts is
whatever lies beneath the menu item.

This is fixed for the game context menu and the game bar's menus, which
now stay open until the dialog has been raised. It can still happen with
the main window's menu button: if the Lutris window is small enough that
**Preferences** or another item hangs outside its edge, the dialog is
not focused. Typing keeps going to the main window, and the dialog's
title bar looks dimmed.

Workaround: click the dialog's title bar once, or enlarge the Lutris
window so the menu fits inside it.
