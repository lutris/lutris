# -*- coding:Utf-8 -*-
from gi.repository import Gtk

from lutris.runners import import_runner
from lutris.gui.configvbox import ConfigVBox


class RunnerConfigVBox(ConfigVBox):
    """ Runner Configuration VBox
        This vbox is used in game configuration and global runner
        configuration.
    """
    def __init__(self, lutris_config, caller):
        runner_classname = lutris_config.runner
        ConfigVBox.__init__(self, runner_classname, caller)
        runner = import_runner(runner_classname)()
        if "runner_options" is not None:
            self.options = runner.runner_options
            self.lutris_config = lutris_config
            self.generate_widgets()
        else:
            warningLabel = Gtk.Label(label="This runner has no options yet\n"
                                     + "Please fix this")
            self.pack_start(warningLabel, True, True, 0)
