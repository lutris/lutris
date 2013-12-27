from lutris.runners.runner import Runner
from lutris.util.system import find_executable


class pcsxr(Runner):
    """PlayStation emulator"""

    package = "pcsxr"
    is_installable = True
    platform = "Playstation"
    game_options = [{
        "option": "iso",
        "type": "file_chooser",
        "label": "iso"
    }]
    runner_options = []

    def get_executable(self):
        candidates = ('pcsx', 'pcsxr')
        for candidate in candidates:
            executable = find_executable(candidate)
            if executable:
                return executable

    def is_installed(self):
        return bool(self.get_executable())

    def play(self):
        """Run Playstation game"""
        iso = self.settings["game"].get("iso")
        executable = self.get_executable()
        command = [executable, " -nogui -cdfile \"" + iso + "\" -runcd"]
        return {'command': command}
