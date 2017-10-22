import os
import subprocess
from lutris.runners.runner import Runner
from lutris.util.display import get_current_resolution
from lutris.util.log import logger
from lutris.util.joypad import get_controller_mappings

class mednafen(Runner):
    human_name = "Mednafen"
    description = ("Multi-system emulator including NES, GB(A), PC Engine "
                   "support.")
    platforms = [
        'Nintendo Game Boy (Color)',
        'Nintendo Game Boy Advance',
        'Sega Game Gear',
        'Sega Genesis/Mega Drive',
        'Atari Lynx',
        'Sega Master System',
        'SNK Neo Geo Pocket (Color)',
        'Nintendo NES',
        'NEC PC Engine TurboGrafx-16',
        'NEC PC-FX',
        'Sony PlayStation',
        'Sega Saturn',
        'Nintendo SNES',
        'Bandai WonderSwan',
        'Nintendo Virtual Boy',
    ]
    machine_choices = (
        ('Game Boy (Color)', 'gb'),
        ('Game Boy Advance', 'gba'),
        ('Game Gear','gg'),
        ('Genesis/Mega Drive','md'),
        ('Lynx', 'lynx'),
        ('Master System','sms'),
        ('Neo Geo Pocket (Color)','gnp'),
        ('NES', 'nes'),
        ('PC Engine', 'pce'),
        ('PC-FX','pcfx'),
        ('PlayStation', 'psx'),
        ('Saturn','ss'),
        ('SNES','snes'),
        ('WonderSwan', 'wswan'),
        ('Virtual Boy','vb'),
    )
    runner_executable = 'mednafen/bin/mednafen'
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
        },
        {
            "option": "dflt_cntrllr",
            "type": "bool",
            "label": "Use Mednafen controller configuration",
            "default": False,
        }

    ]

    def get_platform(self):
        machine = self.game_config.get('machine')
        if machine:
            for index, choice in enumerate(self.machine_choices):
                if choice[1] == machine:
                    return self.platforms[index]
        return ''

    def find_joysticks(self):
        """ Detect connected joysticks and return their ids """
        joy_ids = []
        if not self.is_installed:
            return []
        output = subprocess.Popen([self.get_executable(), "dummy"],
                                  stdout=subprocess.PIPE,
                                  universal_newlines=True).communicate()[0]
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

    def set_joystick_controls(self, joy_ids, machine):
        """ Setup joystick mappings per machine """

        # Get the controller mappings
        mapping = get_controller_mappings()[0][1]

        # Consrtuct a dictionary of button codes to parse to mendafen
        # Joysticks and dpad codes based on the xbox controller
        map_code = {'a':'','b':'','c':'','x':'','y':'','z':'','back':'','start':'',
                'leftshoulder':'','rightshoulder':'','lefttrigger':'',
                'righttrigger':'','leftstick':'','rightstick':'','select':'',
                'shoulder_l':'','shoulder_r':'','i':'','ii':'','iii':'','iv':'',
                'v':'','vi':'','run':'','ls':'','rs':'','fire1':'','fire2':'',
                'option_1':'','option_2':'','cross':'','circle':'','square':'','triangle':'',
                'r1':'','r2':'','l1':'','l2':'','option':'','l':'','r':'',
                'right-x':'','right-y':'','left-x':'','left-y':'',
                'up-x':'','up-y':'','down-x':'','down-y':'',
                'lstick_up':'0000c001',
                'lstick_down':'00008001',
                'lstick_right':'00008000',
                'lstick_left':'0000c000',
                'rstick_up':'0000c003',
                'rstick_down':'00008003',
                'rstick_left':'0000c002',
                'rstick_right':'00008002',
                'dpup':'0000c005',
                'dpdown':'00008005',
                'dpleft':'0000c004',
                'dpright':'00008004'}

        # Insert the button mapping number into the map_codes
        for button in mapping.keys:
            bttn_id = mapping.keys[button]
            if bttn_id[0]=='b': # it's a button
                map_code[button] = '000000'+bttn_id[1:].zfill(2)

        # Duplicate button names that are emulated in mednanfen
        map_code['up'] = map_code['dpup']
        map_code['down'] = map_code['dpdown']
        map_code['left'] = map_code['dpleft']
        map_code['right'] = map_code['dpright']
        map_code['select'] = map_code['back']
        map_code['shoulder_r'] = map_code['rightshoulder']
        map_code['shoulder_l'] = map_code['leftshoulder']
        map_code['i'] = map_code['b']
        map_code['ii'] = map_code['a']
        map_code['iii'] = map_code['leftshoulder']
        map_code['iv'] = map_code['y']
        map_code['v'] = map_code['x']
        map_code['vi'] = map_code['rightshoulder']
        map_code['run'] = map_code['start']
        map_code['ls'] = map_code['leftshoulder']
        map_code['rs'] = map_code['rightshoulder']
        map_code['c'] = map_code['righttrigger']
        map_code['z'] = map_code['lefttrigger']
        map_code['fire1'] = map_code['a']
        map_code['fire2'] = map_code['b']
        map_code['option_1'] = map_code['x']
        map_code['option_2'] = map_code['y']
        map_code['r1'] = map_code['rightshoulder']
        map_code['r2'] = map_code['righttrigger']
        map_code['l1'] = map_code['leftshoulder']
        map_code['l2'] = map_code['lefttrigger']
        map_code['cross'] = map_code['a']
        map_code['circle'] = map_code['b']
        map_code['square'] = map_code['x']
        map_code['triangle'] = map_code['y']
        map_code['option'] = map_code['select']
        map_code['l'] = map_code['leftshoulder']
        map_code['r'] = map_code['rightshoulder']
        map_code['right-x'] = map_code['dpright']
        map_code['left-x'] = map_code['dpleft']
        map_code['up-x'] = map_code['dpup']
        map_code['down-x'] = map_code['dpdown']
        map_code['right-y'] = map_code['lstick_right']
        map_code['left-y'] = map_code['lstick_left']
        map_code['up-y'] = map_code['lstick_up']
        map_code['down-y'] = map_code['lstick_down']

        # Define which buttons to use for each machine
        layout = {
            'nes' : ['a','b','start','select','up','down','left','right'],
            'gb' : ['a','b','start','select','up','down','left','right'],
            'gba' : ['a','b','shoulder_r','shoulder_l','start','select','up','down','left', 'right'],
            'pce' : ['i','ii','iii','iv','v','vi','run','select','up','down','left','right'],
            'ss' : ['a','b','c','x','y','z','ls','rs','start','up','down','left','right'],
            'gg' : ['button1','button2','start','up','down','left','right'],
            'md' : ['a','b','c','x','y','z','start','up','down','left','right'],
            'sms' : ['fire1','fire2','up','down','left','right'],
            'lynx' : ['a','b','option_1','option_2','up','down','left','right'],
            'psx' : ['cross','circle','square','triangle','l1','l2','r1','r2',
                     'start','select','lstick_up','lstick_down','lstick_right',
                     'lstick_left','rstick_up','rstick_down','rstick_left','rstick_right',
                     'up','down','left','right'],
            'pcfx' : ['i','ii','iii','iv','v','vi','run','select','up','down','left','right'],
            'ngp' : ['a','b','option','up','down','left','right'],
            'snes' : ['a','b','x','y','l','r','start','select','up','down','left','right'],
            'wswan' : ['a','b','right-x','right-y','left-x','left-y','up-x','up-y',
                       'down-x','down-y','start']
        }
        # Select a the gamepad type
        controls = []
        if machine in ['gg','lynx','wswan','gb','gba']:
            gamepad = 'builtin.gamepad'
        elif machine in ['md']:
            gamepad = 'gamepad6'
            controls.append('-md.input.port1')
            controls.append('gamepad6')
        elif machine in ['psx']:
            gamepad = 'dualshock'
            controls.append('-psx.input.port1')
            controls.append('dualshock')
        else:
            gamepad = 'gamepad'

        # Construct the controlls options
        for button in layout[machine]:
            controls.append("-{}.input.port1.{}.{}".format(machine,gamepad,button)) 
            controls.append("joystick {} {}".format(joy_ids[0],map_code[button]))
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
        use_dflt_cntrllr = self.runner_config.get('dflt_cntrllr')
        if (len(joy_ids) > 0) and not use_dflt_cntrllr:
            controls = self.set_joystick_controls(joy_ids, machine)
            for control in controls:
                options.append(control)
        else:
            logger.debug("No joystick specification")

        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}

        command = [self.get_executable()]
        for option in options:
            command.append(option)
        command.append(rom)
        return {'command': command}
