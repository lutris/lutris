# To change this template, choose Tools | Templates
# and open the template in the editor.

from wine import wine
import os
__author__ = "strider"
__date__ = "$Oct 6, 2009 12:23:49 PM$"

class steam(wine):

    def __init__(self):
        self.executable = "Steam.exe"
        self.description = "Runs Steam games with Wine"
        self.machine = "Steam Platform"
        super(steam, self).__init__()
        #TODO : Put Steam Path in config file
        self.game_path = "/home/strider/Games/Steam/"
        self.game_exe = "steam.exe"
        self.args = "-silent -applaunch 26800"


    def get_name(self, steam_file):
        data = steam_file.read(1000)
        if "name" in data:
            index_of_name = str.find(data, "name")
            index = index_of_name + 5
            char = "0"
            name = ""
            while ord(char) != 0x0:
                char = data[index]
                index = index + 1
                name = name + char
            return name[:-1]

    def get_appid_from_filename(self, filename):
        if filename.endswith(".vdf"):
            appid = filename[filename.find("_") + 1:filename.find(".")]
        elif filename.endswith('.pkv'):
            appid = filename[:filename.find("_")]
        return  int(appid)

    def get_appid_list(self):
        self.game_list = []
        os.chdir(os.path.join(self.game_path,"appcache"))
        max_counter = 10010
        files = []
        counter = 0
        for file in os.listdir("."):
            counter = counter + 1
            if counter < max_counter:
                files.append(file)
            else:
                break

        steam_apps = []
        for file in files:
            if file.endswith(".vdf"):
                test_file = open(file,"rb")
                appid = self.get_appid_from_filename(file)
                appname = self.get_name(test_file)
                if appname:
                    steam_apps.append((appid,appname,file))
                test_file.close()

        steam_apps.sort()
        steam_apps_file = open(os.path.join(os.path.expanduser("~"),"steamapps.txt"),"w")
        for steam_app in steam_apps:
            #steam_apps_file.write("%d\t%s\n" % (steam_app[0],steam_app[1]))
            #print ("%d\t%s\n" % (steam_app[0],steam_app[1]))
            self.game_list.append((steam_app[0],steam_app[1]))
        steam_apps_file.close()
