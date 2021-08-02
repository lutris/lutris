"""Runner for the PICO-8 fantasy console"""
import json
import math
import os
import shutil
from gettext import gettext as _
from time import sleep

from lutris import settings
from lutris.database.games import get_game_by_field
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.downloader import Downloader
from lutris.util.log import logger
from lutris.util.strings import split_arguments

DOWNLOAD_URL = "https://github.com/daniel-j/lutris-pico-8-runner/archive/master.tar.gz"


class pico8(Runner):
    description = _("Runs PICO-8 fantasy console cartridges")
    multiple_versions = False
    human_name = _("PICO-8")
    platforms = [_("PICO-8")]
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": _("Cartridge file/URL/ID"),
            "help": _("You can put a .p8.png file path, URL, or BBS cartridge ID here."),
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
            "help": _("Launch in fullscreen."),
        },
        {
            "option": "window_size",
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
        {
            "option": "engine",
            "type": "string",
            "label": _("Engine (web only)"),
            "default": "pico8_0111g_4",
            "help": _("Name of engine (will be downloaded) or local file path"),
        },
    ]

    system_options_override = [{"option": "disable_runtime", "default": True}]

    runner_executable = "pico8/web.py"

    def __init__(self, config=None):
        super(pico8, self).__init__(config)

        self.runnable_alone = self.is_native

    def __repr__(self):
        return _("PICO-8 runner (%s)") % self.config

    def install(self, version=None, downloader=None, callback=None):
        opts = {}
        if callback:
            opts["callback"] = callback
        opts["dest"] = settings.RUNNER_DIR + "/pico8"
        opts["merge_single"] = True
        if downloader:
            opts["downloader"] = downloader
        else:
            raise RuntimeError("Unsupported download for this runner")
        self.download_and_extract(DOWNLOAD_URL, **opts)

    @property
    def is_native(self):
        return self.runner_config.get("runner_executable", "") != ""

    @property
    def engine_path(self):
        engine = self.runner_config.get("engine")
        if not engine.lower().endswith(".js") and not os.path.exists(engine):
            engine = os.path.join(
                settings.RUNNER_DIR,
                "pico8/web/engines",
                self.runner_config.get("engine") + ".js",
            )
        return engine

    @property
    def cart_path(self):
        main_file = self.game_config.get("main_file")
        if self.is_native and main_file.startswith("http"):
            return os.path.join(settings.RUNNER_DIR, "pico8/cartridges", "tmp.p8.png")
        if not os.path.exists(main_file) and main_file.isdigit():
            return os.path.join(settings.RUNNER_DIR, "pico8/cartridges", main_file + ".p8.png")
        return main_file

    @property
    def launch_args(self):
        if self.is_native:
            args = [self.get_executable()]
            args.append("-windowed")
            args.append("0" if self.runner_config.get("fullscreen") else "1")
            if self.runner_config.get("splore"):
                args.append("-splore")

            size = self.runner_config.get("window_size").split("x")
            if len(size) == 2:
                args.append("-width")
                args.append(size[0])
                args.append("-height")
                args.append(size[1])
            extra_args = self.runner_config.get("args", "")
            for arg in split_arguments(extra_args):
                args.append(arg)
        else:
            args = [
                self.get_executable(),
                os.path.join(settings.RUNNER_DIR, "pico8/web/player.html"),
                "--window-size",
                self.runner_config.get("window_size"),
            ]
        return args

    def get_run_data(self):
        return {"command": self.launch_args, "env": self.get_env(os_env=False)}

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Checks if pico8 runner is installed and if the pico8 executable available.
        """
        if self.is_native and system.path_exists(self.runner_config.get("runner_executable")):
            return True
        return system.path_exists(os.path.join(settings.RUNNER_DIR, "pico8/web/player.html"))

    def prelaunch(self):
        if not self.game_config.get("main_file") and self.is_installed():
            return True
        if os.path.exists(os.path.join(settings.RUNNER_DIR, "pico8/cartridges", "tmp.p8.png")):
            os.remove(os.path.join(settings.RUNNER_DIR, "pico8/cartridges", "tmp.p8.png"))

        # Don't download cartridge if using web backend and cart is url
        if self.is_native or not self.game_config.get("main_file").startswith("http"):
            if not os.path.exists(self.game_config.get("main_file")) and (
                self.game_config.get("main_file").isdigit() or self.game_config.get("main_file").startswith("http")
            ):
                if not self.game_config.get("main_file").startswith("http"):
                    pid = int(self.game_config.get("main_file"))
                    num = math.floor(pid / 10000)
                    downloadUrl = ("https://www.lexaloffle.com/bbs/cposts/" + str(num) + "/" + str(pid) + ".p8.png")
                else:
                    downloadUrl = self.game_config.get("main_file")
                cartPath = self.cart_path
                system.create_folder(os.path.dirname(cartPath))

                downloadCompleted = False

                def on_downloaded_cart():
                    nonlocal downloadCompleted
                    # If we are offline we don't want an empty file to overwrite the cartridge
                    if dl.downloaded_size:
                        shutil.move(cartPath + ".download", cartPath)
                    else:
                        os.remove(cartPath + ".download")
                    downloadCompleted = True

                dl = Downloader(
                    downloadUrl,
                    cartPath + ".download",
                    True,
                    callback=on_downloaded_cart,
                )
                dl.start()

                # Wait for download to complete or continue if it exists (to work in offline mode)
                while not os.path.exists(cartPath):
                    if downloadCompleted or dl.state == Downloader.ERROR:
                        logger.error("Could not download cartridge from %s", downloadUrl)
                        return False
                    sleep(0.1)

        # Download js engine
        if not self.is_native and not os.path.exists(self.runner_config.get("engine")):
            enginePath = os.path.join(
                settings.RUNNER_DIR,
                "pico8/web/engines",
                self.runner_config.get("engine") + ".js",
            )
            if not os.path.exists(enginePath):
                downloadUrl = ("https://www.lexaloffle.com/bbs/" + self.runner_config.get("engine") + ".js")
                system.create_folder(os.path.dirname(enginePath))
                downloadCompleted = False

                def on_downloaded_engine():
                    nonlocal downloadCompleted
                    downloadCompleted = True

                dl = Downloader(downloadUrl, enginePath, True, callback=on_downloaded_engine)
                dl.start()
                dl.thread.join()  # Doesn't actually wait until finished

                # Waits for download to complete
                while not os.path.exists(enginePath):
                    if downloadCompleted or dl.state == Downloader.ERROR:
                        logger.error("Could not download engine from %s", downloadUrl)
                        return False
                    sleep(0.1)

        return True

    def play(self):
        launch_info = {}
        launch_info["env"] = self.get_env(os_env=False)

        game_data = get_game_by_field(self.config.game_config_id, "configpath")

        command = self.launch_args

        if self.is_native:
            if not self.runner_config.get("splore"):
                command.append("-run")
            cartPath = self.cart_path
            if not os.path.exists(cartPath):
                return {"error": "FILE_NOT_FOUND", "file": cartPath}
            command.append(cartPath)

        else:
            command.append("--name")
            command.append(game_data.get("name") + " - PICO-8")

            # icon = datapath.get_icon_path(game_data.get("slug"))
            # if icon:
            #     command.append("--icon")
            #     command.append(icon)

            webargs = {
                "cartridge": self.cart_path,
                "engine": self.engine_path,
                "fullscreen": self.runner_config.get("fullscreen") is True,
            }
            command.append("--execjs")
            command.append("load_config(" + json.dumps(webargs) + ")")

        launch_info["command"] = command
        return launch_info
