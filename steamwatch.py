import os
import pyinotify

watch_manager = pyinotify.WatchManager()


class EventHandler(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self, event):
        print "MODIFY"
        print event.pathname
        print event

    def process_IN_CREATE(self, event):
        print "CREATE"
        print event.pathname
        print event
        print event.maskname

    def process_IN_DELETE(self, event):
        print "DELETE"
        print event.pathname
        print event

steam_path = os.path.expanduser("~/test")

handler = EventHandler()
# mask = pyinotify.ALL_EVENTS
mask = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY
notifier = pyinotify.Notifier(watch_manager, handler)
wdd = watch_manager.add_watch(steam_path, mask, rec=True)
notifier.loop()
