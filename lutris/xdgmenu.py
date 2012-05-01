import xdg

from xdg.Menu import xdg_config_dirs
from xdg.Menu import Menu

CACHE = xdg.Menu.parse("/etc/xdg/menus/applications.menu")
print CACHE
for entry in CACHE.getEntries():
    print entry
    if str(entry) in ('wine-wine'):
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

RULE = xdg.Menu.Rule(CACHE)
RESULTS = RULE.parseAll()
print RESULTS
