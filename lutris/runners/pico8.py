"""Runner for the PICO-8 fantasy console"""

from gettext import gettext as _
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from lutris import settings
from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import GamePlayInfoDict, RunDataDict, Runner
from lutris.util.downloader import SimpleDownloader
from lutris.util.strings import split_arguments


class pico8(Runner):
    description = _("Runs PICO-8 fantasy console cartridges")
    multiple_versions = False
    human_name = _("PICO-8")
    platform_dict = Runner.to_platform_dict([_("PICO-8")])
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Cartridge file/URL/ID"),
            "help": _("You can put a .p8.png file path, URL, or BBS cartridge ID here."),
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Fullscreen"),
            "default": True,
            "help": _("Launch in fullscreen."),
        },
        {
            "option": "window_size",
            "section": _("Graphics"),
            "label": _("Window size"),
            "type": "string",
            "default": "640x512",
            "help": _("The initial size of the game window."),
        },
        {
            "option": "splore",
            "type": "bool",
            "label": _("Start in splore mode"),
            "default": False,
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Extra arguments"),
            "default": "",
            "help": _("Extra arguments to the executable"),
            "advanced": True,
        },
    ]

    system_executable = "pico8"
    runnable_alone = True

    @property
    def cartridge_url(self) -> str | None:
        cartridge = self.game_config.get("main_file") or ""
        if cartridge.startswith(("https://", "http://")):
            return cartridge
        if cartridge.isascii() and cartridge.isdigit() and not Path(cartridge).is_file():
            return f"https://www.lexaloffle.com/bbs/cposts/{int(cartridge) // 10000}/{cartridge}.p8.png"
        return None

    @property
    def cart_path(self) -> Path:
        if url := self.cartridge_url:
            name = sha256(url.encode()).hexdigest() + ".p8.png"
            return Path(settings.RUNNER_DIR, "pico8", "cartridges", name)
        return Path(self.game_config.get("main_file") or "").expanduser()

    def get_run_data(self) -> RunDataDict:
        command = self.get_command()
        command.extend(("-windowed", "0" if self.runner_config.get("fullscreen") else "1"))
        size = self.runner_config.get("window_size") or "640x512"
        if "x" in size:
            width, height = size.split("x", 1)
            command.extend(("-width", width, "-height", height))
        command.extend(split_arguments(self.runner_config.get("args") or ""))
        if self.runner_config.get("splore"):
            command.append("-splore")
        return {"command": command, "env": self.get_env()}

    def prelaunch(self) -> None:
        super().prelaunch()
        url = self.cartridge_url
        if not url or self.runner_config.get("splore") or self.cart_path.is_file():
            return
        target = self.cart_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=target.parent) as temp:
            download = Path(temp) / target.name
            downloader = SimpleDownloader(url, str(download), overwrite=True)
            downloader.start()
            if not downloader.join() or not download.is_file() or not download.stat().st_size:
                raise MissingGameExecutableError(filename=url)
            download.replace(target)

    def play(self) -> GamePlayInfoDict:
        launch_info = self.get_run_data()
        if self.runner_config.get("splore"):
            return launch_info
        if not self.cartridge_url and not self.cart_path.is_file():
            raise MissingGameExecutableError(filename=str(self.cart_path))
        launch_info["command"].extend(("-run", str(self.cart_path)))
        return launch_info
