import os
from collections import OrderedDict
from configparser import RawConfigParser
from lutris.util.log import logger


class X360ce():
    default_options = OrderedDict([
        ('UseInitBeep', 1),
        ('Log', 0),
        ('Console', 0),
        ('DebugMode', 0),
        ('InternetDatabaseUrl', "http://www.x360ce.com/webservices/x360ce.asmx"),
        ('InternetFeatures', 1),
        ('InternetAutoload', 1),
        ('AllowOnlyOneCopy', 1),
        ('ProgramScanLocations', "C:\Program Files"),
        ('Version', 2),
        ('CombineEnabled', 0),
    ])

    def __init__(self, path=None):
        self.config = RawConfigParser()
        self.config.optionxform = lambda option: option
        if path:
            self.load(path)
        else:
            self.init_defaults()

    def init_defaults(self):
        # Options
        self.config['Options'] = {}
        for option, value in self.default_options.items():
            self.config['Options'][option] = str(value)

        # Input hook
        self.config['InputHook'] = {}
        self.config['InputHook']['HookMode'] = '1'

        # Mappings
        self.config['Mappings'] = {}
        for i in range(1, 5):
            self.config['Mappings']['PAD{}'.format(i)] = ''

        # Pads
        for i in range(1, 5):
            self.config['PAD{}'.format(i)] = {}

    def load(self, path):
        if not os.path.exists(path):
            logger.error("X360ce path %s does not exists")
            return
        self.config.read(path)

    def write(self, path):
        with open(path, 'w') as configfile:
            self.config.write(configfile, space_around_delimiters=False)
