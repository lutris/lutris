# Lutris Modules
from lutris.runners.runner import Runner


class browser(Runner):
    human_name = "Browser"
    platforms = ["Web"]
    description = "Runs games in the browser"
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": "Full address (URL)",
            "help": "The full address of the game's web page.",
        }
    ]
    runner_options = [
        {
            "option":
            "browser",
            "type":
            "file",
            "label":
            "Custom web browser",
            "help": (
                "Select the executable of a browser on your system. \n"
                "If left blank, Lutris will launch your default browser."
            ),
        }
    ]
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def get_executable(self):
        return self.runner_config.get("browser") or "xdg-open"

    def is_installed(self):
        return True

    def play(self):
        url = self.game_config.get("main_file")
        if not url:
            return {
                "error": "CUSTOM",
                "text": ("The web address is empty, \n"
                         "verify the game's configuration."),
            }
        return {"command": [self.get_executable(), url]}
