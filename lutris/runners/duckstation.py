from gettext import gettext as _

from lutris import settings
from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system

from os import path

class duckstation(Runner):
    human_name = _("DuckStation")
    description = _("PlayStation 1 Emulator")
    platforms = [_("Sony PlayStation")]
    runnable_alone = True
    runner_directory = "duckstation"
    runner_executable = runner_directory + "/DuckStation-x64.AppImage"
    settings_directory = path.expanduser("~/.local/share/" + runner_directory)
    bios_directory = path.join(settings_directory, "bios")
    download_url = "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage"
    jp_bios_url = "https://github.com/Abdess/retroarch_system/raw/libretro/Sony%20-%20PlayStation/scph1000.bin"
    us_bios_url = "https://github.com/Abdess/retroarch_system/raw/libretro/Sony%20-%20PlayStation/scph1001.bin"
    eu_bios_url = "https://github.com/Abdess/retroarch_system/raw/libretro/Sony%20-%20PlayStation/scph1002.bin"
    
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ISO file"),
            "help": _("The game image, commonly called a ISO image."),
            "default_path": "game_path",
        }
    ]
    
    runner_options = [
        {
            "option": "bigpicture",
            "type": "bool",
            "label": _("Big Picture"),
            "help": _("Automatically starts big picture UI."),
            "default": False,
        },
        {
            "option": "nogui",
            "type": "bool",
            "label": _("No GUI"),
            "help": _("Disables main window from being shown, exits on shutdown."),
            "default": False,
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "help": _("Enters fullscreen mode immediately after starting."),
            "default": True,
        },
        {
            "option": "fastboot",
            "type": "bool",
            "label": _("Fast Boot"),
            "help": _("Force fast boot for provided filename."),
            "default": False,
        },
    ]
    
    system_options_override = [
        {
            "option": "disable_runtime",
            "default": True,
        },
    ]

    def install(self, install_ui_delegate, version=None, callback=None):
        def on_runner_installed(*_args):
            if not path.isdir(self.bios_directory):
                system.create_folder(self.bios_directory)
            jp_bios_archive = path.join(self.bios_directory, "scph1000.bin")
            us_bios_archive = path.join(self.bios_directory, "scph1001.bin")
            eu_bios_archive = path.join(self.bios_directory, "scph1002.bin")
            install_ui_delegate.download_install_file(self.jp_bios_url, jp_bios_archive)
            install_ui_delegate.download_install_file(self.us_bios_url, us_bios_archive)
            install_ui_delegate.download_install_file(self.eu_bios_url, eu_bios_archive)
            if not system.path_exists(jp_bios_archive):
                raise RuntimeError(_("Could not download PlayStation Japanese BIOS archive"))
            if not system.path_exists(us_bios_archive):
                raise RuntimeError(_("Could not download PlayStation American BIOS archive"))
            if not system.path_exists(eu_bios_archive):
                raise RuntimeError(_("Could not download PlayStation European BIOS archive"))
            if callback:
                callback()

        super().install(install_ui_delegate, version, on_runner_installed)
    
    def uninstall(self, uninstall_callback=None):
        if path.isdir(self.settings_directory):
            system.delete_folder(self.settings_directory)
        if path.isdir(path.join(settings.RUNNER_DIR, self.runner_directory)):
            system.delete_folder(path.join(settings.RUNNER_DIR, self.runner_directory))
        uninstall_callback()

    def run(self, ui_delegate):
        initial_arguments = self.get_command()
        
        # Big Picture
        if self.runner_config.get("bigpicture"):
            initial_arguments.append("-bigpicture")
        system.execute(initial_arguments)

    def play(self):
        arguments = self.get_command()
        
        # Big Picture
        if self.runner_config.get("bigpicture"):
            arguments.append("-bigpicture")
        # No GUI
        if self.runner_config.get("nogui"):
            arguments.append("-nogui")
        # Fullscreen
        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        # Fast Boot
        if self.runner_config.get("fastboot"):
            arguments.append("-fastboot")

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            raise MissingGameExecutableError(filename=iso)
        arguments.append(iso)
        return {"command": arguments}
