import os
import subprocess
from lutris.runners.runner import Runner
from lutris.util.display import get_current_resolution
from lutris.util.log import logger


class mednafen(Runner):
    human_name = "Mednafen"
    description = ("Multi-system emulator including NES, GB(A), PC Engine "
                   "support.")
    platform = ("Atari Lynx, GameBoy, GameBoy Color, "
                "GameBoy Advance, NES, PC Engine (TurboGrafx 16), PC-FX, "
                "SuperGrafx, NeoGeo Pocket, NeoGeo Pocket Color, WonderSwan")
    runner_executable = 'mednafen/bin/mednafen'
    machine_choices = (
        ("NES", "nes"),
        ("PC Engine", "pce"),
        ('Game Boy', 'gb'),
        ('Game Boy Advance', 'gba'),
        ('Playstation', 'psx')
    )
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            'help': ("The game data, commonly called a ROM image. \n"
                     "Mednafen supports GZIP and ZIP compressed ROMs.")
        },
        {
            "option": "machine",
            "type": "choice",
            "label": "Machine type",
            "choices": machine_choices,
            'help': ("The emulated machine.")
        }
    ]
    runner_options = [
        {
            "option": "fs",
            "type": "bool",
            "label": "Fullscreen",
            "default": False,
        },
        {
            "option": "stretch",
            "type": "choice",
            "label": "Aspect ratio",
            "choices": (
                ("Disabled", "0"),
                ("Stretched", "full"),
                ("Preserve aspect ratio", "aspect"),
                ("Integer scale", "aspect_int"),
                ("Multiple of 2 scale", "aspect_mult2"),
            ),
            "default": "0"
        },
        {
            "option": "scaler",
            "type": "choice",
            "label": "Video scaler",
            "choices": (
                ("none", "none"),
                ("hq2x", "hq2x"),
                ("hq3x", "hq3x"),
                ("hq4x", "hq4x"),
                ("scale2x", "scale2x"),
                ("scale3x", "scale3x"),
                ("scale4x", "scale4x"),
                ("2xsai", "2xsai"),
                ("super2xsai", "super2xsai"),
                ("supereagle", "supereagle"),
                ("nn2x", "nn2x"),
                ("nn3x", "nn3x"),
                ("nn4x", "nn4x"),
                ("nny2x", "nny2x"),
                ("nny3x", "nny3x"),
                ("nny4x", "nny4x"),
            ),
            "default": "hq4x",
        }
    ]

    def find_joysticks(self):
        """ Detect connected joysticks and return their ids """
        joy_ids = []
        if not self.is_installed:
            return []
        output = subprocess.Popen([self.get_executable(), "dummy"],
                                  stdout=subprocess.PIPE).communicate()[0]
        ouput = str(output).split("\n")
        found = False
        joy_list = []
        for line in ouput:
            if found and "Joystick" in line:
                joy_list.append(line)
            else:
                found = False
            if "Initializing joysticks" in line:
                found = True

        for joy in joy_list:
            index = joy.find("Unique ID:")
            joy_id = joy[index + 11:]
            logger.debug('Joystick found id %s ' % joy_id)
            joy_ids.append(joy_id)
        return joy_ids

    def set_joystick_controls(self, joy_ids, machine):
        """ Setup joystick mappings per machine """

        # Button mappings (based on Xbox360 controller)
        BTN_A = "00000000"
        BTN_B = "00000001"
        # BTN_X = "00000002"
        # BTN_Y = "00000003"
        BTN_R = "00000004"
        BTN_L = "00000005"
        BTN_SELECT = "00000006"
        BTN_START = "00000007"
        # BTN_HOME = "00000008"
        # BTN_THUMB_L = "00000009"
        # BTN_THUMB_R = "00000010"
        AXIS_UP = "0000c001"
        AXIS_DOWN = "00008001"
        AXIS_LEFT = "0000c000"
        AXIS_RIGHT = "00008000"

        nes_controls = [
            "-nes.input.port1.gamepad.a",
            "joystick {} {}".format(joy_ids[0], BTN_B),
            "-nes.input.port1.gamepad.b",
            "joystick {} {}".format(joy_ids[0], BTN_A),
            "-nes.input.port1.gamepad.start",
            "joystick {} {}".format(joy_ids[0], BTN_START),
            "-nes.input.port1.gamepad.select",
            "joystick {} {}".format(joy_ids[0], BTN_SELECT),
            "-nes.input.port1.gamepad.up",
            "joystick {} {}".format(joy_ids[0], AXIS_UP),
            "-nes.input.port1.gamepad.down",
            "joystick {} {}".format(joy_ids[0], AXIS_DOWN),
            "-nes.input.port1.gamepad.left",
            "joystick {} {}".format(joy_ids[0], AXIS_LEFT),
            "-nes.input.port1.gamepad.right",
            "joystick {} {}".format(joy_ids[0], AXIS_RIGHT),
        ]

        gba_controls = [
            "-gba.input.builtin.gamepad.a",
            "joystick {} {}".format(joy_ids[0], BTN_B),
            "-gba.input.builtin.gamepad.b",
            "joystick {} {}".format(joy_ids[0], BTN_A),
            "-gba.input.builtin.gamepad.shoulder_r",
            "joystick {} {}".format(joy_ids[0], BTN_R),
            "-gba.input.builtin.gamepad.shoulder_l",
            "joystick {} {}".format(joy_ids[0], BTN_L),
            "-gba.input.builtin.gamepad.start",
            "joystick {} {}".format(joy_ids[0], BTN_START),
            "-gba.input.builtin.gamepad.select",
            "joystick {} {}".format(joy_ids[0], BTN_SELECT),
            "-gba.input.builtin.gamepad.up",
            "joystick {} {}".format(joy_ids[0], AXIS_UP),
            "-gba.input.builtin.gamepad.down",
            "joystick {} {}".format(joy_ids[0], AXIS_DOWN),
            "-gba.input.builtin.gamepad.left",
            "joystick {} {}".format(joy_ids[0], AXIS_LEFT),
            "-gba.input.builtin.gamepad.right",
            "joystick {} {}".format(joy_ids[0], AXIS_RIGHT),
        ]

        gb_controls = [
            "-gb.input.builtin.gamepad.a",
            "joystick {} {}".format(joy_ids[0], BTN_B),
            "-gb.input.builtin.gamepad.b",
            "joystick {} {}".format(joy_ids[0], BTN_A),
            "-gb.input.builtin.gamepad.start",
            "joystick {} {}".format(joy_ids[0], BTN_START),
            "-gb.input.builtin.gamepad.select",
            "joystick {} {}".format(joy_ids[0], BTN_SELECT),
            "-gb.input.builtin.gamepad.up",
            "joystick {} {}".format(joy_ids[0], AXIS_UP),
            "-gb.input.builtin.gamepad.down",
            "joystick {} {}".format(joy_ids[0], AXIS_DOWN),
            "-gb.input.builtin.gamepad.left",
            "joystick {} {}".format(joy_ids[0], AXIS_LEFT),
            "-gb.input.builtin.gamepad.right",
            "joystick {} {}".format(joy_ids[0], AXIS_RIGHT),
        ]

        pce_controls = [
            "-pce.input.port1.gamepad.i",
            "joystick {} {}".format(joy_ids[0], BTN_B),
            "-pce.input.port1.gamepad.ii",
            "joystick {} {}".format(joy_ids[0], BTN_A),
            "-pce.input.port1.gamepad.run",
            "joystick {} {}".format(joy_ids[0], BTN_START),
            "-pce.input.port1.gamepad.select",
            "joystick {} {}".format(joy_ids[0], BTN_SELECT),
            "-pce.input.port1.gamepad.up",
            "joystick {} {}".format(joy_ids[0], AXIS_UP),
            "-pce.input.port1.gamepad.down",
            "joystick {} {}".format(joy_ids[0], AXIS_DOWN),
            "-pce.input.port1.gamepad.left",
            "joystick {} {}".format(joy_ids[0], AXIS_LEFT),
            "-pce.input.port1.gamepad.right",
            "joystick {} {}".format(joy_ids[0], AXIS_RIGHT),
        ]

        if machine == "pce":
            controls = pce_controls
        elif machine == "nes":
            controls = nes_controls
        elif machine == "gba":
            controls = gba_controls
        elif machine == "gb":
            controls = gb_controls
        else:
            controls = []
        return controls

    def play(self):
        """Runs the game"""
        rom = self.game_config.get('main_file') or ''
        machine = self.game_config.get('machine') or ''

        fullscreen = self.runner_config.get("fs") or "0"
        if fullscreen is True:
            fullscreen = "1"
        elif fullscreen is False:
            fullscreen = "0"

        stretch = self.runner_config.get('stretch') or "0"
        scaler = self.runner_config.get('scaler') or "hq4x"

        resolution = get_current_resolution()
        (resolutionx, resolutiony) = resolution.split("x")
        xres = str(resolutionx)
        yres = str(resolutiony)
        options = ["-fs", fullscreen,
                   "-" + machine + ".xres", xres,
                   "-" + machine + ".yres", yres,
                   "-" + machine + ".stretch", stretch,
                   "-" + machine + ".special", scaler,
                   "-" + machine + ".videoip", "1"]
        joy_ids = self.find_joysticks()
        if len(joy_ids) > 0:
            controls = self.set_joystick_controls(joy_ids, machine)
            for control in controls:
                options.append(control)
        else:
            logger.debug("No Joystick found")

        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}

        command = [self.get_executable()]
        for option in options:
            command.append(option)
        command.append(rom)
        return {'command': command}
