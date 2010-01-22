import gtk, apt, apt.progress.gtk2
class InstallerWindow(gtk.Window):
    def __init__(self,pkg_name):
        gtk.Window.__init__(self)
        self.set_decorated(False)
        self.progress = apt.progress.gtk2.GtkAptProgress()
        self.add(self.progress)
        self.show_all()
        cache = apt.cache.Cache(self.progress.open)
        if not cache[pkg_name].isInstalled:
            cache[pkg_name].markInstall()
        cache.commit(self.progress.fetch, self.progress.install)

if __name__ == "__main__":
    win = InstallerWindow("sdlmame")
    gtk.main()
