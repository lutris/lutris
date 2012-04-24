from xdg.Menu import MenuEntryCache, Menu
from xdg.Menu import xdg_config_dirs
import xdg
from xdg import BaseDirectory

print xdg_config_dirs

cache = xdg.Menu.parse("/etc/xdg/menus/applications.menu")
print cache
for entry in cache.getEntries():
    #print entry
    if str(entry) == 'Games':
        print("youpi")
        for game in entry.getEntries():
            print "============"
            print game
            #print dir(game)
            if isinstance(game, xdg.Menu.MenuEntry):
                print game.getType()
                print game.getDir()
                print dir(game)
                print unicode(game.DesktopEntry)
                desktop_entry = game.DesktopEntry
                print "Icon", desktop_entry.getIcon()
                print "DesktopFileID", game.DesktopFileID
                print "Filename", game.Filename
                print "Path", desktop_entry.getPath()
                print "Exec", desktop_entry.getExec()
            else:
                print game.__class__

r = xdg.Menu.Rule(cache)
results = r.parseAll()
print results
