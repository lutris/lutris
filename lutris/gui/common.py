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

import gtk

class QuestionDialog(gtk.Dialog):
    def __init__(self,settings):
        gtk.Dialog.__init__(self)
        self.set_title(settings['title'])
        self.set_size_request(300,300)
        self.question_hbox = gtk.HBox();
        self.question_label = gtk.Label(settings['question'])
        self.question_entry = gtk.Entry()
        self.question_hbox.pack_start(self.question_label)
        self.question_hbox.pack_start(self.question_entry)
        self.vbox.pack_start(self.question_hbox)
        self.show_all();
        
    def show(self):
        gtk.main()
        
        
if __name__ == "__main__":
    settings = { 'title': 'My Question', 'question': '???' }
    qd = QuestionDialog(settings) 
    qd.show()
           
