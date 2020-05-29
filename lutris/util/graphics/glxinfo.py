"""Parser for the glxinfo utility"""
# Standard Library
import subprocess

# Lutris Modules
from lutris.util.log import logger


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
        self._attrs = set()  # Keep a reference of the created attributes
        self.parse()

    @staticmethod
    def get_glxinfo_output():
        """Return the glxinfo -B output"""
        try:
            return subprocess.check_output(["glxinfo", "-B"]).decode()
        except subprocess.CalledProcessError as ex:
            logger.error("glxinfo call failed: %s", ex)
            return ""

    def as_dict(self):
        """Return the attributes as a dict"""
        return {attr: getattr(self, attr) for attr in self._attrs}

    def parse(self):
        """Converts the glxinfo output to class attributes"""
        if not self._output:
            logger.error("No available glxinfo output")
            return
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
            self._attrs.add(key.lower())
            setattr(self, key.lower(), value)
