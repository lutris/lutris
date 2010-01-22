###############################################################################
## Lutris video gaming platform
##
## Copyright (C) 2009, 2010 Mathieu Comandon <strycore@gmail.com>
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

__author__="strider"
__date__ ="$28 nov. 2009 05:29:44$"

from tool.url_tool import UrlTool
from tool.re_tool import RE_tool
import urllib2

import os

class GoogleImage():
    """A neat class to fetch 21 thumbnails from Google Image and easily retrieve
    the full image.
    """
    def __init__(self):
        self.google_results = []

    def get_google_image_page(self,search_string):
        self.url_tool = UrlTool()
        self.url_tool.local = False
        #self.url_tool.set_local_file("/home/strider/result.html")
        
        # "Everybody stand back"
        # "I know regular expressions"
        # Python !  *tap* *tap*
        # "Wait, forgot to escape a space."  Wheeeeee[taptaptap]eeeeee.
        self.webpage = self.url_tool.read_html("http://images.google.fr/images?q="+urllib2.quote(search_string)+"&oe=utf-8&rls=com.ubuntu:fr:official&client=firefox-a&um=1&ie=UTF-8&sa=N&hl=en&tab=wi")
        #file("/home/strider/result.html","w").write(self.webpage)
        
    def scan_for_images(self,dest):
        re_tool = RE_tool()
        images = re_tool.findall("\[\"/imgres\?imgurl\\\\x3d(.*?)\\\\x26imgrefurl\\\\x3d(.*?)\\\\x3d1\",\"\",\"(.*?)\".*?http://(.*?)(\d+ x \d+ - \d+[bkm]).*?\"(.*?)\".*?http://(.*?)\",.*?\]", self.webpage)
        self.google_results = []
        index = 0
        for image in images:
            print "Fetching image %i / 21" % index
            thumbnail = "http://"+image[6]+"?q=tbn:"+image[2]+image[0]
            url = image[0]
            size = image[4]
            format  = image[5]
            self.google_results.append({"url":url,"size":size,"format":format,"thumbnail":thumbnail})
            self.url_tool.save_to(os.path.join(dest,str(index)+".jpg"),thumbnail)
            index = index + 1

    def get_pic_at(self,index,dest):
        self.url_tool.save_to(dest+"."+self.google_results[index]["url"].split(".")[-1],self.google_results[index]["url"])