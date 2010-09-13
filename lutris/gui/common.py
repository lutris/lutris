# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

import pygtk
import gtk
import apt.progress.gtk2


class NoticeDialog:
    def __init__(self, message):
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

class ErrorDialog:
    def __init__(self, message):
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

class QuestionDialog:
    def __init__(self,settings):
        dialog = gtk.MessageDialog(
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_YES_NO,
                message_format=settings['question']
            )
        dialog.set_title(settings['title'])
        self.result = dialog.run()
        dialog.destroy()

