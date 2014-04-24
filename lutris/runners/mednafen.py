import os
import subprocess
from lutris.runners.runner import Runner
from lutris.util.display import get_current_resolution
from lutris.util.log import logger


class mednafen(Runner):
    """Mednafen is a multi-system emulator, including NES, GB(A), PC Engine"""
    executable = "mednafen"
    platform = (
        "Atari Lynx, GameBoy, GameBoy Color, "
        "GameBoy Advance, NES, PC Engine (TurboGrafx 16), PC-FX, "
        "SuperGrafx, NeoGeo Pocket, NeoGeo Pocket Color, WonderSwan"
    )
    package = "mednafen"
    machine_choices = (
        ("NES", "nes"),
        ("PC Engine", "pce"),
        ('Game Boy', 'gb'),
        ('Game Boy Advance', 'gba')
    )
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "Rom file"
        },
        {
            "option": "machine",
            "type": "one_choice",
            "label": "Machine type",
            "choices": machine_choices
        }
    ]
    runner_options = [
        {
            "option": "fs",
            "type": "bool",
            "label": "Fullscreen",
            "default": True,
        }
    ]

    def find_joysticks(self):
        """ Detect connected joysticks and return their ids """
        joy_ids = []
        if not self.is_installed:
            return []
        output = subprocess.Popen(["mednafen", "dummy"],
                                  stdout=subprocess.PIPE).communicate()[0]
        ouput = output.split("\n")
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

    def set_joystick_controls(self, joy_ids):
        """ Setup joystick mappings per machine """
        nes_controls = [
            "-nes.input.port1.gamepad.a",
            "\"joystick " + joy_ids[0] + " 00000001\"",
            "-nes.input.port1.gamepad.b",
            "\"joystick " + joy_ids[0] + " 00000002\"",
            "-nes.input.port1.gamepad.start",
            "\"joystick " + joy_ids[0] + " 00000009\"",
            "-nes.input.port1.gamepad.select",
            "\"joystick " + joy_ids[0] + " 00000008\"",
            "-nes.input.port1.gamepad.up",
            "\"joystick " + joy_ids[0] + " 0000c001\"",
            "-nes.input.port1.gamepad.down",
            "\"joystick " + joy_ids[0] + " 00008001\"",
            "-nes.input.port1.gamepad.left",
            "\"joystick " + joy_ids[0] + " 0000c000\"",
            "-nes.input.port1.gamepad.right",
            "\"joystick " + joy_ids[0] + " 00008000\""
        ]

        gba_controls = [
            "-gba.input.builtin.gamepad.a",
            "\"joystick " + joy_ids[0] + " 00000001\"",
            "-gba.input.builtin.gamepad.b",
            "\"joystick " + joy_ids[0] + " 00000002\"",
            "-gba.input.builtin.gamepad.shoulder_r",
            "\"joystick " + joy_ids[0] + " 00000007\"",
            "-gba.input.builtin.gamepad.shoulder_l",
            "\"joystick " + joy_ids[0] + " 00000006\"",
            "-gba.input.builtin.gamepad.start",
            "\"joystick " + joy_ids[0] + " 00000009\"",
            "-gba.input.builtin.gamepad.select",
            "\"joystick " + joy_ids[0] + " 00000008\"",
            "-gba.input.builtin.gamepad.up",
            "\"joystick " + joy_ids[0] + " 0000c001\"",
            "-gba.input.builtin.gamepad.down",
            "\"joystick " + joy_ids[0] + " 00008001\"",
            "-gba.input.builtin.gamepad.left",
            "\"joystick " + joy_ids[0] + " 0000c000\"",
            "-gba.input.builtin.gamepad.right",
            "\"joystick " + joy_ids[0] + " 00008000\""
        ]

        gb_controls = [
            "-gb.input.builtin.gamepad.a",
            "\"joystick " + joy_ids[0] + " 00000001\"",
            "-gb.input.builtin.gamepad.b",
            "\"joystick " + joy_ids[0] + " 00000002\"",
            "-gb.input.builtin.gamepad.start",
            "\"joystick " + joy_ids[0] + " 00000009\"",
            "-gb.input.builtin.gamepad.select",
            "\"joystick " + joy_ids[0] + " 00000008\"",
            "-gb.input.builtin.gamepad.up",
            "\"joystick " + joy_ids[0] + " 0000c001\"",
            "-gb.input.builtin.gamepad.down",
            "\"joystick " + joy_ids[0] + " 00008001\"",
            "-gb.input.builtin.gamepad.left",
            "\"joystick " + joy_ids[0] + " 0000c000\"",
            "-gb.input.builtin.gamepad.right",
            "\"joystick " + joy_ids[0] + " 00008000\""
        ]

        pce_controls = [
            "-pce.input.port1.gamepad.i",
            "\"joystick " + joy_ids[0] + " 00000001\"",
            "-pce.input.port1.gamepad.ii",
            "\"joystick " + joy_ids[0] + " 00000002\"",
            "-pce.input.port1.gamepad.run",
            "\"joystick " + joy_ids[0] + " 00000009\"",
            "-pce.input.port1.gamepad.select",
            "\"joystick " + joy_ids[0] + " 00000008\"",
            "-pce.input.port1.gamepad.up",
            "\"joystick " + joy_ids[0] + " 0000c001\"",
            "-pce.input.port1.gamepad.down",
            "\"joystick " + joy_ids[0] + " 00008001\"",
            "-pce.input.port1.gamepad.left",
            "\"joystick " + joy_ids[0] + " 0000c000\"",
            "-pce.input.port1.gamepad.right",
            "\"joystick " + joy_ids[0] + " 00008000\""
        ]

        if self.machine == "pce":
            controls = pce_controls
        elif self.machine == "nes":
            controls = nes_controls
        elif self.machine == "gba":
            controls = gba_controls
        elif self.machine == "gb":
            controls = gb_controls
        else:
            controls = []
        return controls

    def play(self):
        """Runs the game"""
        rom = self.settings["game"]["main_file"]
        machine = self.settings["game"]["machine"]

        if self.runner_config.get("fs"):
            fullscreen = "1"
        else:
            fullscreen = "0"
        resolution = get_current_resolution()
        (resolutionx, resolutiony) = resolution.split("x")
        xres = str(resolutionx)
        yres = str(resolutiony)
        options = ["-fs", fullscreen,
                   "-" + machine + ".xres", xres,
                   "-" + machine + ".yres", yres,
                   "-" + machine + ".stretch", "1",
                   "-" + machine + ".special", "hq4x",
                   "-" + machine + ".videoip", "1"]
        joy_ids = self.find_joysticks()
        if len(joy_ids) > 0:
            controls = self.set_joystick_controls(joy_ids)
            for control in controls:
                options.append(control)
        else:
            logger.debug("No Joystick found")

        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}

        command = [self.executable]
        for option in options:
            command.append(option)
        command.append("\"%s\"" % rom)
        return {'command': command}
