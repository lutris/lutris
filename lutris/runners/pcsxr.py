import os
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util.system import find_executable


class pcsxr(Runner):
    """PlayStation emulator"""
    package = "pcsxr"
    is_installable = True
    platform = "Playstation"
    game_options = [{
        "option": "iso",
        "type": "file",
        "label": "iso"
    }]
    runner_options = []

    def get_executable(self):
        # Lutris provided emulator
        pcsxr_path = os.path.join(settings.RUNNER_DIR, 'pcsxr/pcsxr')
        if os.path.exists(pcsxr_path):
            return pcsxr_path
        # System wide available emulator
        candidates = ('pcsx', 'pcsxr')
        for candidate in candidates:
            executable = find_executable(candidate)
            if executable:
                return executable

    def play(self):
        """Run Playstation game"""
        iso = self.settings["game"].get("iso")
        command = [self.get_executable(),
                   " -nogui -cdfile \"" + iso + "\" -runcd"]
        return {'command': command}
