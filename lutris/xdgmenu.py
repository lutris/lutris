"""Get games available from the XDG menu."""

import subprocess
from gi.repository import Gio

IGNORED_ENTRIES = ("lutris", "mame", "dosbox", "steam", "playonlinux")


def get_xdg_games():
    """Return the list of games stored in the XDG menu."""
    xdg_games = []

    apps = Gio.AppInfo.get_all()
    for app in apps:
        if app.get_name().lower() in IGNORED_ENTRIES:
            continue
        categories = app.get_categories()
        if not categories or not 'Game' in categories:
            continue

        exe_and_args = app.get_string('Exec').split(' ', 2)
        if len(exe_and_args) == 1:
            exe, args = exe_and_args[0], ''
        else:
            exe, args = exe_and_args
        if not exe.startswith('/'):
            exe = subprocess.Popen("which '%s'" % exe, stdout=subprocess.PIPE,
                                   shell=True).communicate()[0].strip('\n')
        xdg_games.append((app.get_display_name(), exe, args))
    return xdg_games

if __name__ == '__main__':

    print get_xdg_games()
