from lutris.runners.runner import Runner


class rpcs3(Runner):
    human_name = "rpcs3"
    description = "PlayStation 3 emulator"
    platforms = ["Sony PlayStation 3"]
    runnable_alone = True
    runner_executable = "rpcs3/rpcs3"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "Path to EBOOT.BIN",
        }
    ]

    # RPCS3 currently uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def play(self):
        return {"command": [self.get_executable(), self.game_config.get("main_file")]}
