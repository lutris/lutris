import os
import subprocess

from lutris.util.log import logger
from lutris.settings import CACHE_DIR
from lutris.runners.runner import Runner


def set_regedit(path, key, value):
    """Plays with the windows registry

    path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
    """

    logger.debug("Setting wine registry key : %s\\%s to %s",
                 path, key, value)
    reg_path = os.path.join(CACHE_DIR, 'winekeys.reg')
    #Make temporary reg file
    reg_file = open(reg_path, "w")
    reg_file.write("""REGEDIT4

[%s]
"%s"="%s"

""" % (path, key, value))
    reg_file.close()
    subprocess.call(["wine", "regedit", reg_path])
    os.remove(reg_path)


def create_prefix(prefix_path):
    """Create a new wineprefix"""
    os.system("export WINEPREFIX=\"%s\"; wineboot"
              % prefix_path)


def wineexec(executable, args="", prefix=None):
    if not prefix:
        prefix = ""
    else:
        prefix = "WINEPREFIX=\"%s\" " % prefix
    command = prefix + "wine \"%s\" %s" % (executable, args)
    logger.debug("Running wine command: %s", command)
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).communicate()


def winetricks(app, prefix=None):
    if not prefix:
        prefix = ""
    else:
        prefix = "WINEPREFIX=\"%s\" " % prefix
    command = prefix + "winetricks %s" % app
    logger.debug("Running winetricks command: %s", command)
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).communicate()


def kill():
    """The kill command runs wineserver -k"""
    os.popen("winserver -k")


# pylint: disable=C0103
class wine(Runner):
    '''Run Windows games with Wine'''
    executable = 'wine'
    platform = 'Windows'
    game_options = [
        {
            'option': 'exe',
            'type': 'file_chooser',
            'label': 'Executable'
        },
        {
            'option': 'args',
            'type': 'string',
            'label': 'Arguments'
        },
        {
            'option': 'prefix',
            'type': 'directory_chooser',
            'label': 'Prefix'
        }
    ]

    def __init__(self, settings=None):
        super(wine, self).__init__()

        mouse_warp_choices = [('Disable', 'disable'),
                              ('Enable', 'enable'),
                              ('Force', 'force')]
        orm_choices = [('BackBuffer', 'backbuffer'),
                       ('FBO', 'fbo'),
                       ('PBuffer', 'pbuffer')]
        rtlm_choices = [('Auto', 'auto'),
                        ('Disabled', 'disabled'),
                        ('ReadDraw', 'readdraw'),
                        ('ReadTex', 'readtex'),
                        ('TexDraw', 'texdraw'),
                        ('TexTex', 'textex')]
        multisampling_choices = [('Enabled', 'enabled'),
                                 ("Disabled", "disabled")]
        audio_choices = [('Alsa', 'alsa'),
                         ('OSS', 'oss'),
                         ('Jack', 'jack')]
        desktop_choices = [('Yes', 'Default'),
                           ('No', 'None')]
        self.runner_options = [
            {
                'option': 'cdrom_path',
                'label': 'CDRom mount point',
                'type': 'directory_chooser'
            },
            {
                'option': 'MouseWarpOverride',
                'label': 'Mouse Warp Override',
                'type': 'one_choice',
                'choices': mouse_warp_choices
            },
            {
                'option': 'Multisampling',
                'label': 'Multisampling',
                'type': 'one_choice',
                'choices': multisampling_choices
            },
            {
                'option': 'OffscreenRenderingMode',
                'label': 'Offscreen Rendering Mode',
                'type': 'one_choice',
                'choices': orm_choices
            },
            {
                'option': 'RenderTargetLockMode',
                'label': 'Render Target Lock Mode',
                'type': 'one_choice',
                'choices': rtlm_choices
            },
            {
                'option': 'Audio',
                'label': 'Audio driver',
                'type': 'one_choice',
                'choices': audio_choices
            },
            {
                'option': 'Desktop',
                'label': 'Virtual desktop',
                'type': 'one_choice',
                'choices': desktop_choices
            }
        ]
        self.settings = settings
        reg_prefix = "HKEY_CURRENT_USER\Software\Wine"
        self.reg_keys = {
            "RenderTargetLockMode": r"%s\Direct3D" % reg_prefix,
            "Audio": r"%s\Drivers" % reg_prefix,
            "MouseWarpOverride": r"%s\DirectInput" % reg_prefix,
            "Multisampling": r"%s\Direct3D" % reg_prefix,
            "OffscreenRenderingMode": r"%s\Direct3D" % reg_prefix,
            "DirectDrawRenderer": r"%s\Direct3D" % reg_prefix,
            "Version": r"%s" % reg_prefix,
            "Desktop": r"%s\Explorer" % reg_prefix
        }

    def get_install_command(self, exe=None):
        """Return the installer command, either from an exe or an iso"""
        if exe:
            command = "%s %s" % (self.executable, exe)
        else:
            print("Need an executable file")
            return False
        return command

    @classmethod
    def msi_exec(cls, msi_file, quiet=False, prefix=None):
        msi_args = ["msiexec", "/i", msi_file]
        if quiet:
            msi_args.append("/q")
        return wineexec(msi_args, prefix)

    def check_regedit_keys(self, wine_config):
        """Resets regedit keys according to config"""
        for key in self.reg_keys.keys():
            if key in wine_config:
                set_regedit(self.reg_keys[key], key, wine_config[key])

    def prepare_launch(self):
        if self.__class__.__name__ in self.settings.config:
            wine_config = self.settings.config[self.__class__.__name__]
        else:
            wine_config = {}
        self.check_regedit_keys(wine_config)

    def play(self):
        game_exe = self.settings['game'].get('exe')
        arguments = self.settings['game'].get('args', "")
        self.prepare_launch()

        command = []
        prefix = self.settings['game'].get('prefix', "")
        if os.path.exists(prefix):
            command.append("WINEPREFIX=\"%s\" " % prefix)

        self.game_path = os.path.dirname(game_exe)
        game_exe = os.path.basename(game_exe)
        if not os.path.exists(self.game_path):
            if prefix:
                self.game_path = os.path.join(prefix, self.game_path)
            if not os.path.exists(self.game_path):
                return {"error": "FILE_NOT_FOUND", "file": self.game_path}

        command.append(self.executable)
        command.append("\"" + game_exe + "\"")
        if arguments:
            for arg in arguments.split():
                command.append(arg)
        return {'command': command}
