from lutris.runners.runner import Runner


class pcsxr(Runner):
    """PlayStation emulator"""

    executable = "pcsxr"
    package = "pcsxr"
    is_installable = True
    platform = "Playstation"
    game_options = [{
        "option": "iso",
        "type": "file_chooser",
        "label": "iso"
    }]
    runner_options = []

    def play(self):
        """Run Playstation game"""
        iso = self.settings["game"].get("iso")
        command = [self.executable, " -nogui -cdfile \"" + iso + "\" -runcd"]
        return {'command': command}
