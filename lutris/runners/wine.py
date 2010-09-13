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

import os
import logging
import lutris.constants
from lutris.runners.runner import Runner
class wine(Runner):
    def __init__(self,settings = None):
        self.executable = "wine"
        self.package = "wine"
        self.machine = "Windows games"
        self.description = "Run Windows games with Wine"

        self.is_installable = True

        self.installer_options = [{
            "option": "installer",
            "type": "single",
            "label": "Executable"
        }]

        self.game_options = [
                {"option": "exe","type":"single", "label":"Executable"},
                {"option": "args", "type": "string", "label": "Arguments" }
        ]

        mouse_warp_choices = [
                ("Disable","disable"),
                ("Enable","enable"),
                ("Force","force")
        ]
        orm_choices = [
                ("BackBuffer","backbuffer"),
                ("FBO","fbo"),
                ("PBuffer","pbuffer")
        ]
        rtlm_choices = [
                ("Auto","auto"),
                ("Disabled","disabled"),
                ("ReadDraw","readdraw"),
                ("ReadTex","readtex"),
                ("TexDraw","texdraw"),
                ("TexTex","textex")
        ]
        multisampling_choices = [
                ("Enabled","enabled"),
                ("Disabled","disabled")
        ]
        audio_choices = [
                ("Alsa","alsa"),
                ("OSS","oss"),
                ("Jack","jack")
        ]
        self.runner_options = [
                {
                    "option": "cdrom_path",
                    "label": "CDRom mount point",
                    "type": "directory_chooser"
                },
                {
                    "option": "MouseWarpOverride",
                    "label": "Mouse Warp Override",
                    "type": "one_choice",
                    "choices": mouse_warp_choices
                },
                {
                    "option": "Multisampling",
                    "label": "Multisampling",
                    "type": "one_choice",
                    "choices": multisampling_choices
                },
                {
                    "option": "OffscreenRenderingMode",
                    "label": "Offscreen Rendering Mode",
                    "type": "one_choice",
                    "choices": orm_choices
                },
                {
                    "option": "RenderTargetLockMode",
                    "label": "Render Target Lock Mode",
                    "type": "one_choice",
                    "choices": rtlm_choices
                },
                {
                    "option": "Audio",
                    "label": "Audio driver",
                    "type": "one_choice",
                    "choices": audio_choices
                }
        ]

        if settings:
            self.gameExe = settings["game"]["exe"]
            if "args" in settings.config["game"]:
                self.args = settings["game"]["args"]
            else:
                self.args = None
            if "wine" in settings.config:
                self.wine_config = settings.config["wine"]
            else:
                self.wine_config = None

    def set_regedit(self,path,key,value):
        """Plays with the windows registry
        path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
        """

        os.chdir(lutris.constants.tmp_path)
        #Make temporary reg file
        logging.debug("Setting wine registry key : %s\\%s to %s" 
                % (path, key, value))
        reg_file = open("wine_tmp.reg","w")
        reg_file.write("""REGEDIT4
[%s]
"%s"="%s"
""" % (path,key,value))
        reg_file.close()
        reg_path = os.path.join(lutris.constants.tmp_path,"wine_tmp.reg")
        os.popen(self.executable + " regedit " + reg_path )
        #os.remove(reg_path)

    def kill(self):
        """The kill command runs wineserver -k"""
        os.popen("winserver -k")

    def get_install_command(self,installer_executable):
        command = "%s %s" % (self.executable, installer_executable)
        return command

    def play(self):
        if "MouseWarpOverride" in self.wine_config:
            self.set_regedit(
                    r"HKEY_CURRENT_USER\Software\Wine\DirectInput",
                    "MouseWarpOverride",
                    self.wine_config["MouseWarpOverride"]
                )

        if "Audio" in self.wine_config:
            self.set_regedit(
                    r"[HKEY_CURRENT_USER\Software\Wine\Drivers]",
                    "Audio",
                    self.wine_config["Audio"]
                )

        if "Multisampling" in self.wine_config:
            self.set_regedit(
                    r"[HKEY_CURRENT_USER\Software\Wine\Direct3D]",
                    "Multisampling",
                    self.wine_config["Multisampling"]
                )

        if "RenderTargetLockMode" in self.wine_config:
            self.set_regedit(
                    r"[HKEY_CURRENT_USER\Software\Wine\Direct3D]",
                    "RenderTargetLockMode",
                    self.wine_config["RenderTargetLockMode"]
                )

        if "OffscreenRenderingMode" in self.wine_config:
            self.set_regedit(
                    r"[HKEY_CURRENT_USER\Software\Wine\Direct3D]",
                    "OffscreenRenderingMode",
                    self.wine_config["OffscreenRenderingMode"]
                )

        if "DirectDrawRenderer" in self.wine_config:
            self.set_regedit(
                    r"[HKEY_CURRENT_USER\Software\Wine\Direct3D]",
                    "DirectDrawRenderer",
                    self.wine_config["DirectDrawRenderer"]
                )

        if "Version" in self.wine_config:
            self.set_regedit(
                    r"[HKEY_CURRENT_USER\Software\Wine]",
                    "Version",
                    self.wine_config["Version"]
                )
        self.game_path = os.path.dirname(self.gameExe)
        game_exe = os.path.basename(self.gameExe)

        command = [self.executable,"\""+game_exe+"\""]
        if self.args:
            for arg in self.args.split():
                command.append(arg)
        return command

