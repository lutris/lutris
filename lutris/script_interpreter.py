#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import yaml
import urlparse
import os
import hashlib
import logging
import lutris.constants

from lutris.tool.url_tool import UrlTool

class LutrisInterpreter():
    def __init__(self, filename = None):
        self.valid_schemes = ('http', 'https', 'ftp')
        self.url_tool = UrlTool()
        self.files = {}
        self.dirs = {}
        self.dirs['cache'] = lutris.constants.cache_path
        self.dirs['gamedir'] = '/home/strider/Jeux'

        if filename:
            self.load(filename)

    def load(self,filename):
        self.config = yaml.load(file(filename, 'r').read())

    def get_files(self):
        if not self.config:
            return False
        if 'files' in self.config:
            for filename in self.config['files']:
                file_id = filename.keys()[0]
                file_path = filename[file_id]
                url = urlparse.urlparse(file_path)
                if url.scheme:
                    destfile = os.path.basename(url.path)
                    destpath = lutris.constants.cache_path + destfile
                    if not os.path.exists(destpath):
                        self.url_tool.save_to(destpath,file_path)
                    self.files[file_id] = destpath
                else:
                    print 'not a url', file_id

    def install(self):
        if not 'installer' in self.config:
            return False
        for directive in self.config['installer']:
            directive_name = directive.keys()[0]
            print directive_name
            if directive_name == 'md5_check':
                self.md5_check(directive)
            if directive_name == 'extract':
                extract_info = directive['extract']
                if 'newdir' in extract_info:
                    dest = os.path.join(self.dirs[extract_info['destination']],extract_info['newdir'])
                    if not os.path.exists(dest):
                        os.mkdir(dest)
                    self.dirs[extract_info['newdir']] = dest
                else:
                    dest = self.dirs[extract_info['destination']]
                self.extract(extract_info['file'], dest)

    def check_md5(self, file_id):
        print 'checking ', self.files[file_id]

    def extract(self,archive,dest,options = {}):
        if not 'method' in options:
            method = 'zip'
        else:
            method = options['method']
        print "extracting %s to %s " % (self.files[archive], dest )
        command = "unzip %s -d  %s"%(self.files[archive], dest)
        os.system(command)

    def move(self,source, destination):
        os.move

if __name__ == '__main__':
    filename = '/home/strider/Jeux/quake.lutris'
    interpreter = LutrisInterpreter(filename)
    interpreter.get_files()
    interpreter.install()

