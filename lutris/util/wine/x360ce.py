"""Module to setup and interact with X360CE"""
from collections import OrderedDict
from configparser import RawConfigParser
from lutris.util import system
from lutris.util.log import logger
from lutris.util.joypad import get_controller_mappings


class X360ce:
    default_options = OrderedDict(
        [
            ("UseInitBeep", 1),
            ("Log", 0),
            ("Console", 0),
            ("DebugMode", 0),
            ("InternetDatabaseUrl", "http://www.x360ce.com/webservices/x360ce.asmx"),
            ("InternetFeatures", 1),
            ("InternetAutoload", 1),
            ("AllowOnlyOneCopy", 1),
            ("ProgramScanLocations", "C:\\Program Files"),
            ("Version", 2),
            ("CombineEnabled", 0),
        ]
    )

    default_controller = OrderedDict(
        [
            ("ControllerType", "1"),
            ("PassThrough", "0"),
            ("ForcesPassThrough", "0"),
            ("PassThroughIndex", "0"),
            ("Right Trigger DeadZone", "8"),
            ("Left Trigger DeadZone", "8"),
            ("Combined", "0"),
            ("CombinedIndex", "0"),
            ("A DeadZone", "0"),
            ("B DeadZone", "0"),
            ("X DeadZone", "0"),
            ("Y DeadZone", "0"),
            ("Start DeadZone", "0"),
            ("Back DeadZone", "0"),
            ("Left Shoulder DeadZone", "0"),
            ("Left Thumb DeadZone", "0"),
            ("Right Shoulder DeadZone", "0"),
            ("Right Thumb DeadZone", "0"),
            ("AxisToDPadDownDeadZone", "0"),
            ("AxisToDPadLeftDeadZone", "0"),
            ("AxisToDPadRightDeadZone", "0"),
            ("AxisToDPadUpDeadZone", "0"),
            ("AxisToDPad", "0"),
            ("AxisToDPadDeadZone", "256"),
            ("AxisToDPadOffset", "0"),
            ("Left Analog X+ Button", "0"),
            ("Left Analog X- Button", "0"),
            ("Left Analog Y+ Button", "0"),
            ("Left Analog Y- Button", "0"),
            ("Left Analog X DeadZone", "4915"),
            ("Left Analog Y DeadZone", "4915"),
            ("Left Analog X AntiDeadZone", "0"),
            ("Left Analog Y AntiDeadZone", "0"),
            ("Left Analog X Linear", "0"),
            ("Left Analog Y Linear", "0"),
            ("Right Analog X+ Button", "0"),
            ("Right Analog X- Button", "0"),
            ("Right Analog Y+ Button", "0"),
            ("Right Analog Y- Button", "0"),
            ("Right Analog X DeadZone", "4915"),
            ("Right Analog Y DeadZone", "4915"),
            ("Right Analog X AntiDeadZone", "0"),
            ("Right Analog Y AntiDeadZone", "0"),
            ("Right Analog X Linear", "0"),
            ("Right Analog Y Linear", "0"),
            ("UseForceFeedback", "1"),
            ("FFBType", "1"),
            ("SwapMotor", "0"),
            ("ForcePercent", "100"),
            ("LeftMotorDirection", "0"),
            ("LeftMotorStrength", "100"),
            ("LeftMotorPeriod", "120"),
            ("RightMotorDirection", "0"),
            ("RightMotorStrength", "100"),
            ("RightMotorPeriod", "60"),
            ("D-pad POV", "1"),
        ]
    )

    gamecontroller_map = {
        "leftx": "Left Analog X",
        "lefty": "Left Analog Y",
        "rightx": "Right Analog X",
        "righty": "Right Analog Y",
        "dpup": "D-pad Up",
        "dpdown": "D-pad Down",
        "dpleft": "D-pad Left",
        "dpright": "D-pad Right",
        "a": "A",
        "b": "B",
        "x": "X",
        "y": "Y",
        "back": "Back",
        "start": "Start",
        "guide": "Guide",
        "leftshoulder": "Left Shoulder",
        "lefttrigger": "Left Trigger",
        "leftstick": "Left Thumb",
        "rightshoulder": "Right Shoulder",
        "righttrigger": "Right Trigger",
        "rightstick": "Right Thumb",
    }

    def __init__(self, path=None):
        self.config = RawConfigParser()
        self.config.optionxform = lambda option: option
        if path:
            self.load(path)
        else:
            self.init_defaults()

    def init_defaults(self):
        # Options
        self.config["Options"] = {}
        for option, value in self.default_options.items():
            self.config["Options"][option] = str(value)

        # Input hook
        self.config["InputHook"] = {}
        self.config["InputHook"]["HookMode"] = "1"

        # Mappings
        self.config["Mappings"] = {}
        for i in range(1, 5):
            self.config["Mappings"]["PAD{}".format(i)] = ""

        # Pads
        for i in range(1, 5):
            self.config["PAD{}".format(i)] = {}

    def load(self, path):
        if not system.path_exists(path):
            logger.error("X360ce path %s does not exists")
            return
        self.config.read(path)

    def write(self, path):
        with open(path, "w") as configfile:
            self.config.write(configfile, space_around_delimiters=False)

    def populate_controllers(self):
        controllers = get_controller_mappings()

        # Controllers are listed in reverse order in x360ce
        for index, (device, mappings) in enumerate(controllers[::-1]):
            self.load_mappings(device, mappings, index + 1)

    @staticmethod
    def convert_sdl_key(sdl_key):
        # Buttons
        if sdl_key.startswith("b"):
            return str(int(sdl_key[1:]) + 1)

        # D-pad
        if sdl_key.startswith("h"):
            return "d{}".format("{0:b}".format(int(sdl_key[3:]))[::-1].index("1") + 1)

        # Axis
        if sdl_key.startswith("a"):
            return "x{}".format(int(sdl_key[1:]) + 1)

    def load_mappings(self, device, mappings, index=1):
        product_guid = "{:04x}{:04x}-0000-0000-0000-504944564944".format(
            device.info.product, device.info.vendor
        )
        instance_guid = "9e573eda-7734-11d{}-8d4a-23903fb6bdf7".format(index + 1)
        section_name = "IG_{}".format(instance_guid.replace("-", ""))
        self.config["Mappings"]["PAD{}".format(index)] = section_name
        self.config[section_name] = {}
        self.config[section_name]["ProductName"] = "{} (event)".format(device.name)
        self.config[section_name]["ProductGuid"] = product_guid
        self.config[section_name]["InstanceGuid"] = instance_guid

        for option, value in self.default_controller.items():
            self.config[section_name][option] = str(value)

        for xinput_key, sdl_key in mappings.keys.items():
            if xinput_key == "platform":
                continue
            xinput_name = self.gamecontroller_map.get(xinput_key)
            if not xinput_name:
                logger.warning("No mapping for %s", xinput_key)
            button_name = self.convert_sdl_key(sdl_key)
            if button_name.startswith("x"):
                if xinput_name.endswith("Y"):
                    button_name = button_name.replace("x", "x-")
                if xinput_name.endswith("Trigger"):
                    button_name = button_name.replace("x", "a")
            self.config[section_name][xinput_name] = button_name
