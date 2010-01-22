import os
from ftplib import FTP

class FTPFetch():
    def __init__(self):
        self.destination_path = "/home/strider/Games/mame"

    def append_file(self, data):
        """
        Callback function to save files on local drive
        """
        file = open(self.romname, "a")
        file.write(data)
        file.close()

    def fetch(self, global_conf, pattern=None):
        """
        Get files matching pattern from FTP Server
        """
        ftp_source = FTP(global_conf["ftphost"])
        ftp_source.login(global_conf["ftplogin"], global_conf["ftppassword"])
        ftp_source.cwd(global_conf["mamedir"])
        game_list = ftp_source.nlst()
        os.chdir(self.destination_path)
        for game in game_list:
            if pattern in game:
                self.romname = game
                ftp_source.retrbinary("RETR " + game, self.append_file)
        ftp_source.close()