"""Directory management for runners"""


class RunnerDirectory:

    """Class to reference and manipulate directories used by folders"""

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return self.path


# That's it for now. There's literally no code at all. Still figuring things
# out here.
