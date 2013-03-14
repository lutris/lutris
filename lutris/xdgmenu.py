"""Get games available from the XDG menu"""
import xdg.Menu
import locale
import subprocess

IGNORED_ENTRIES = ["lutris", "mame", "dosbox", "steam"]

locale._strxfrm = locale.strxfrm


def strxfrm(s):
    """Monkey patch to address an encoding bug in pyxdg (fixed in current
    trunk)"""
    return locale._strxfrm(s.encode('utf-8'))
locale.strxfrm = strxfrm


def get_main_menu():
    return xdg.Menu.parse()


def get_game_entries(menu):
    menu_entries = [entry for entry in menu.getEntries()]
    game_entries = []
    for entry in menu_entries:
        if hasattr(entry, 'Categories') and 'Game' in entry.Categories:
            game_entries.append(entry)
        elif hasattr(entry, 'getEntries') and entry.getName() == 'Games':
            game_entries += get_game_entries(entry)
    return game_entries


def get_xdg_games():
    """Return list of games stored in the XDG menu."""
    xdg_games = []
    for game in get_game_entries(get_main_menu()):

        if not isinstance(game, xdg.Menu.MenuEntry):
            continue
        entry_name = str(game)[:-(len(".desktop"))]
        if entry_name in IGNORED_ENTRIES:
            continue
        desktop_entry = game.DesktopEntry
        game_name = unicode(desktop_entry)
        exe_and_args = desktop_entry.getExec().split(' ', 2)
        if len(exe_and_args) == 1:
            exe = exe_and_args[0]
            args = ''
        else:
            exe, args = exe_and_args
        if not exe.startswith('/'):
            exe = subprocess.Popen("which '%s'" % exe, stdout=subprocess.PIPE,
                                   shell=True).communicate()[0].strip('\n')
        xdg_games.append((game_name, exe, args))
    return xdg_games

if __name__ == '__main__':

    print get_xdg_games()
