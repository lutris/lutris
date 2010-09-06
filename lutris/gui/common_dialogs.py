import gtk

class NoticeDialog:
    def __init__(self, message):
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()
