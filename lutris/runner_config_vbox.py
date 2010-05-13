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

import lutris.runners
from lutris.config_vbox import ConfigVBox
import gtk

class RunnerConfigVBox(ConfigVBox):
    def __init__(self,lutris_config,caller):
        runner = lutris_config.runner
        ConfigVBox.__init__(self,runner,caller)
        runner_instance = eval("lutris.runners."+runner+"."+runner+"()")
        if hasattr(runner_instance, "runner_options"):
            self.options = runner_instance.runner_options
        else:
            warningLabel = gtk.Label("This runner has no options yet\nPlease fix this")
            self.pack_start(warningLabel)
            return
        self.lutris_config = lutris_config
        self.generate_widgets()


        
