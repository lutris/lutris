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


import subprocess
import platform
import hashlib
import logging
try:
    from lutris.config import LutrisConfig
except:
    print "HOPE YOU ARE RUNNING TESTS !!!!!!!!"

class Runner(object):
    '''Generic runner (base class for other runners) '''
    def __init__(self,settings=None):
        ''' Initialize runner'''
        self.executable = None
        self.is_installable = False
        self.arguments = []
        self.error_messages = []
        
    def load(self,game):
        self.game = game

    def play(self):
        pass
    
    def is_installed(self):
        """ Check if runner is installed"""
        is_installed = None
        if not self.executable:
            return 
        cmdline = "which " + self.executable
        cmdline = str.split(cmdline," ")
        result = subprocess.Popen(cmdline,stdout=subprocess.PIPE).communicate()[0]
        if result == '' :
            is_installed = False
        else:
            is_installed = True
        return is_installed

    def get_game_options(self):
        return None

    def get_runner_options(self):
        return None

    def md5sum(self,filename):
        m = hashlib.md5()
        fd = open(filename,"rb")
        content = fd.readlines()
        fd.close()
        for line in content:
            m.update(line)
        return m.hexdigest()

    def install_runner(self):
        """Generic install method, for use with package management systems"""
        #Return false if runner has no package, must be then another method and
        # install method should be overridden by the specific runner
        if not hasattr(self,"package"):
            return False
        linux_dist = platform.linux_distribution()[0]
        #Add the package manager with arguments for your favorite distro :)
        if linux_dist == "Ubuntu" or linux_dist == "Debian":
            package_manager = "apt-get"
            install_args = "-y install"
        elif linux_dist == "Fedora":
            package_manager = "yum"
            install_args = "install"
        else:
            logging.error("""The distro you're running is not supported yet.\n Edit runners/runner.py to add support for it""")
            return False
        print subprocess.Popen("gksu \"%s %s %s\"" % (package_manager,install_args,self.package),shell=True,stdout=subprocess.PIPE).communicate()[0]

    def write_config(self,id,name,fullpath):
        """Writes game config to settings directory"""
        system = self.__class__.__name__
        index= fullpath.rindex("/")
        exe = fullpath[index+1:]
        path = fullpath[:index]
        if path.startswith("file://"):
            path = path[7:]
        gameConfig = LutrisConfig()
        values = {"main":{ "path":path, "exe":exe, "realname" : name, "system":system }}
        gameConfig.write_game_config(id, values)
