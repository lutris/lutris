"""Parser for the glxinfo utility"""
import subprocess

class Container:  # pylint: disable=too-few-public-methods
    """A dummy container for data"""


class GlxInfo:
    """Give access to the glxinfo information"""
    def __init__(self, output=None):
        """Creates a new GlxInfo object

        Params:
            output (str): If provided, use this as the glxinfo output instead
                          of running the program, useful for testing.
        """
        self._output = output or self.get_glxinfo_output()
        self._section = None
        self.parse()

    @staticmethod
    def get_glxinfo_output():
        """Return the glxinfo -B output"""
        return subprocess.check_output(["glxinfo", "-B"]).decode()

    def parse(self):
        """Converts the glxinfo output to class attributes"""
        if not self._output:
            raise ValueError("Missing glxinfo output")
        # Fix glxinfo output (Great, you saved one line by
        # combining display and screen)
        output = self._output.replace("  screen", "\nscreen")
        for line in output.split("\n"):
            if not line.strip():
                continue

            key, value = line.split(":", 1)
            key = key.replace(" string", "").replace(" ", "_")
            value = value.strip()

            if not value and key.startswith(("Extended_renderer_info", "Memory_info")):
                self._section = key[key.index("(") + 1:-1]
                setattr(self, self._section, Container())
                continue
            if self._section:
                if not key.startswith("____"):
                    self._section = None
                else:
                    setattr(getattr(self, self._section), key.strip("_").lower(), value)
                    continue
            setattr(self, key.lower(), value)
