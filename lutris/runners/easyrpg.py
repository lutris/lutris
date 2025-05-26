# Standard Library
from gettext import gettext as _
from os import path

from lutris.exceptions import DirectoryNotFoundError, GameConfigError, MissingGameExecutableError

# Lutris Modules
from lutris.runners.runner import Runner


class easyrpg(Runner):
    human_name = _("EasyRPG Player")
    description = _("Runs RPG Maker 2000/2003 games")
    platforms = [_("Linux")]
    runnable_alone = True
    entry_point_option = "project_path"
    runner_executable = "easyrpg/easyrpg-player"
    download_url = "https://easyrpg.org/downloads/player/0.8/easyrpg-player-0.8-linux.tar.gz"

    game_options = [
        {
            "option": "project_path",
            "type": "directory",
            "label": _("Game directory"),
            "help": _("Select the directory of the game. <b>(required)</b>"),
        },
        {
            "option": "encoding",
            "type": "choice",
            "advanced": True,
            "label": _("Encoding"),
            "help": _(
                "Instead of auto detecting the encoding or using the one in RPG_RT.ini, the specified encoding is used."
            ),
            "choices": [
                (_("Auto"), ""),
                (_("Auto (ignore RPG_RT.ini)"), "auto"),
                (_("Western European"), "1252"),
                (_("Central/Eastern European"), "1250"),
                (_("Japanese"), "932"),
                (_("Cyrillic"), "1251"),
                (_("Korean"), "949"),
                (_("Chinese (Simplified)"), "936"),
                (_("Chinese (Traditional)"), "950"),
                (_("Greek"), "1253"),
                (_("Turkish"), "1254"),
                (_("Hebrew"), "1255"),
                (_("Arabic"), "1256"),
                (_("Baltic"), "1257"),
                (_("Thai"), "874"),
            ],
            "default": "",
        },
        {
            "option": "engine",
            "type": "choice",
            "advanced": True,
            "label": _("Engine"),
            "help": _("Disable auto detection of the simulated engine."),
            "choices": [
                (_("Auto"), ""),
                (_("RPG Maker 2000 engine (v1.00 - v1.10)"), "rpg2k"),
                (_("RPG Maker 2000 engine (v1.50 - v1.51)"), "rpg2kv150"),
                (_("RPG Maker 2000 (English release) engine"), "rpg2ke"),
                (_("RPG Maker 2003 engine (v1.00 - v1.04)"), "rpg2k3"),
                (_("RPG Maker 2003 engine (v1.05 - v1.09a)"), "rpg2k3v105"),
                (_("RPG Maker 2003 (English release) engine"), "rpg2k3e"),
            ],
            "default": "",
        },
        {
            "option": "patch",
            "type": "string",
            "advanced": True,
            "label": _("Patches"),
            "help": _(
                "Instead of autodetecting patches used by this game, force emulation of certain patches.\n"
                "\nAvailable patches:\n"
                '<b>common-this</b>: "This Event" in common events'
                "<b>dynrpg</b>: DynRPG patch by Cherry"
                "<b>key-patch</b>: Key Patch by Ineluki"
                "<b>maniac</b>: Maniac Patch by BingShan"
                "<b>pic-unlock</b>: Pictures are not blocked by messages"
                "<b>rpg2k3-cmds</b>: Support all RPG Maker 2003 event commands in any version of the engine"
                "\n\nYou can provide multiple patches or use 'none' to disable all engine patches."
            ),
        },
        {
            "option": "language",
            "type": "string",
            "advanced": True,
            "label": _("Language"),
            "help": _("Load the game translation in the language/LANG directory."),
        },
        {
            "option": "save_path",
            "type": "directory",
            "label": _("Save path"),
            "warn_if_non_writable_parent": True,
            "help": _(
                "Instead of storing save files in the game directory they are stored in the specified path. "
                "The directory must exist."
            ),
        },
        {
            "option": "new_game",
            "type": "bool",
            "label": _("New game"),
            "help": _("Skip the title scene and start a new game directly."),
            "default": False,
        },
        {
            "option": "load_game_id",
            "type": "range",
            "label": _("Load game ID"),
            "help": _("Skip the title scene and load SaveXX.lsd.\nSet to 0 to disable."),
            "min": 0,
            "max": 99,
            "default": 0,
        },
        {
            "option": "record_input",
            "type": "file",
            "advanced": True,
            "label": _("Record input"),
            "help": _("Records all button input to the specified log file."),
        },
        {
            "option": "replay_input",
            "type": "file",
            "advanced": True,
            "label": _("Replay input"),
            "help": _(
                "Replays button input from the specified log file, as generated by 'Record input'.\n"
                "If the RNG seed and the state of the save file directory is also the same as it was "
                "when the log was recorded, this should reproduce an identical run to the one recorded."
            ),
        },
        {
            "option": "test_play",
            "type": "bool",
            "advanced": True,
            "section": _("Debug"),
            "label": _("Test play"),
            "help": _("Enable TestPlay (debug) mode."),
            "default": False,
        },
        {
            "option": "hide_title",
            "type": "bool",
            "advanced": True,
            "section": _("Debug"),
            "label": _("Hide title"),
            "help": _("Hide the title background image and center the command menu."),
            "default": False,
        },
        {
            "option": "start_map_id",
            "type": "range",
            "advanced": True,
            "section": _("Debug"),
            "label": _("Start map ID"),
            "help": _(
                "Overwrite the map used for new games and use MapXXXX.lmu instead.\n"
                "Set to 0 to disable.\n\n"
                "Incompatible with 'Load game ID'."
            ),
            "min": 0,
            "max": 9999,
            "default": 0,
        },
        {
            "option": "start_position",
            "type": "string",
            "advanced": True,
            "section": _("Debug"),
            "label": _("Start position"),
            "help": _(
                "Overwrite the party start position and move the party to the specified position.\n"
                "Provide two numbers separated by a space.\n\n"
                "Incompatible with 'Load game ID'."
            ),
        },
        {
            "option": "start_party",
            "type": "string",
            "advanced": True,
            "section": _("Debug"),
            "label": _("Start party"),
            "help": _(
                "Overwrite the starting party members with the actors with the specified IDs.\n"
                "Provide one to four numbers separated by spaces.\n\n"
                "Incompatible with 'Load game ID'."
            ),
        },
        {
            "option": "battle_test",
            "type": "string",
            "advanced": True,
            "section": _("Debug"),
            "label": _("Battle test"),
            "help": _("Start a battle test with the specified monster party."),
        },
    ]

    runner_options = [
        {
            "option": "autobattle_algo",
            "type": "choice",
            "advanced": True,
            "section": _("Engine"),
            "label": _("AutoBattle algorithm"),
            "help": _(
                "Which AutoBattle algorithm to use.\n\n"
                "<b>RPG_RT</b>: The default RPG_RT compatible algorithm, including RPG_RT bugs.\n"
                "<b>RPG_RT+</b>: The default RPG_RT compatible algorithm, with bug-fixes.\n"
                "<b>ATTACK</b>: Like RPG_RT+ but only physical attacks, no skills."
            ),
            "choices": [
                (_("Auto"), ""),
                (_("RPG_RT"), "RPG_RT"),
                (_("RPG_RT+"), "RPG_RT+"),
                (_("ATTACK"), "ATTACK"),
            ],
            "default": "",
        },
        {
            "option": "enemyai_algo",
            "type": "choice",
            "advanced": True,
            "section": _("Engine"),
            "label": _("EnemyAI algorithm"),
            "help": _(
                "Which EnemyAI algorithm to use.\n\n"
                "<b>RPG_RT</b>: The default RPG_RT compatible algorithm, including RPG_RT bugs.\n"
                "<b>RPG_RT+</b>: The default RPG_RT compatible algorithm, with bug-fixes.\n"
            ),
            "choices": [
                (_("Auto"), ""),
                (_("RPG_RT"), "RPG_RT"),
                (_("RPG_RT+"), "RPG_RT+"),
            ],
            "default": "",
        },
        {
            "option": "seed",
            "type": "range",
            "advanced": True,
            "section": _("Engine"),
            "label": _("RNG seed"),
            "help": _("Seeds the random number generator.\nUse -1 to disable."),
            "min": -1,
            "max": 2147483647,
            "default": -1,
        },
        {
            "option": "audio",
            "type": "bool",
            "section": _("Audio"),
            "label": _("Enable audio"),
            "help": _("Switch off to disable audio."),
            "default": True,
        },
        {
            "option": "music_volume",
            "type": "range",
            "section": _("Audio"),
            "label": _("BGM volume"),
            "help": _("Volume of the background music."),
            "min": 0,
            "max": 100,
            "default": 100,
        },
        {
            "option": "sound_volume",
            "type": "range",
            "section": _("Audio"),
            "label": _("SFX volume"),
            "help": _("Volume of the sound effects."),
            "min": 0,
            "max": 100,
            "default": 100,
        },
        {
            "option": "soundfont",
            "type": "file",
            "advanced": True,
            "section": _("Audio"),
            "label": _("Soundfont"),
            "help": _("Soundfont in sf2 format to use when playing MIDI files."),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Fullscreen"),
            "help": _("Start in fullscreen mode."),
            "default": False,
        },
        {
            "option": "game_resolution",
            "type": "choice",
            "section": _("Graphics"),
            "advanced": True,
            "label": _("Game resolution"),
            "help": _(
                "Force a different game resolution.\n\nThis is experimental and can cause glitches or break games!"
            ),
            "choices": [
                (_("320×240 (4:3, Original)"), "original"),
                (_("416×240 (16:9, Widescreen)"), "widescreen"),
                (_("560×240 (21:9, Ultrawide)"), "ultrawide"),
            ],
            "default": "original",
        },
        {
            "option": "scaling",
            "type": "choice",
            "section": _("Graphics"),
            "label": _("Scaling"),
            "help": _(
                "How the video output is scaled.\n\n"
                "<b>Nearest</b>: Scale to screen size (causes scaling artifacts)\n"
                "<b>Integer</b>: Scale to multiple of the game resolution\n"
                "<b>Bilinear</b>: Like Nearest, but output is blurred to avoid artifacts\n"
            ),
            "choices": [
                (_("Nearest"), "nearest"),
                (_("Integer"), "integer"),
                (_("Bilinear"), "bilinear"),
            ],
            "default": "bilinear",
        },
        {
            "option": "stretch",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Stretch"),
            "help": _("Ignore the aspect ratio and stretch video output to the entire width of the screen."),
            "default": False,
        },
        {
            "option": "vsync",
            "type": "bool",
            "section": _("Graphics"),
            "label": _("Enable VSync"),
            "help": _("Switch off to disable VSync and use the FPS limit."),
            "default": True,
        },
        {
            "option": "fps_limit",
            "type": "range",
            "section": _("Graphics"),
            "label": _("FPS limit"),
            "help": _(
                "Set a custom frames per second limit.\n"
                "If unspecified, the default is 60 FPS.\n"
                "Set to 0 to disable the frame limiter."
            ),
            "min": 0,
            "max": 9999,
            "default": 60,
        },
        {
            "option": "show_fps",
            "type": "choice",
            "section": _("Graphics"),
            "label": _("Show FPS"),
            "help": _("Enable frames per second counter."),
            "choices": [
                (_("Disabled"), "off"),
                (_("Fullscreen & title bar"), "on"),
                (_("Fullscreen, title bar & window"), "full"),
            ],
            "default": "off",
        },
        {
            "option": "rtp",
            "type": "bool",
            "section": _("Runtime Package"),
            "label": _("Enable RTP"),
            "help": _("Switch off to disable support for the Runtime Package (RTP)."),
            "default": True,
        },
        {
            "option": "rpg2k_rtp_path",
            "type": "directory",
            "section": _("Runtime Package"),
            "label": _("RPG2000 RTP location"),
            "help": _("Full path to a directory containing an extracted RPG Maker 2000 Run-Time-Package (RTP)."),
        },
        {
            "option": "rpg2k3_rtp_path",
            "type": "directory",
            "section": _("Runtime Package"),
            "label": _("RPG2003 RTP location"),
            "help": _("Full path to a directory containing an extracted RPG Maker 2003 Run-Time-Package (RTP)."),
        },
        {
            "option": "rpg_rtp_path",
            "type": "directory",
            "section": _("Runtime Package"),
            "label": _("Fallback RTP location"),
            "help": _("Full path to a directory containing a combined RTP."),
        },
    ]

    @property
    def game_path(self):
        game_path = self.game_data.get("directory")
        if game_path:
            return path.expanduser(game_path)  # just in case

        # Default to the directory of the entry point
        entry_point = self.game_config.get(self.entry_point_option)
        if entry_point:
            return path.expanduser(entry_point)

        return ""

    def get_env(self, os_env=False, disable_runtime=False):
        env = super().get_env(os_env, disable_runtime=disable_runtime)

        rpg2k_rtp_path = self.runner_config.get("rpg2k_rtp_path")
        if rpg2k_rtp_path:
            env["RPG2K_RTP_PATH"] = rpg2k_rtp_path

        rpg2k3_rtp_path = self.runner_config.get("rpg2k3_rtp_path")
        if rpg2k3_rtp_path:
            env["RPG2K3_RTP_PATH"] = rpg2k3_rtp_path

        rpg_rtp_path = self.runner_config.get("rpg_rtp_path")
        if rpg_rtp_path:
            env["RPG_RTP_PATH"] = rpg_rtp_path

        return env

    def get_command(self):
        cmd = super().get_command()

        # Engine
        autobattle_algo = self.runner_config.get("autobattle_algo")
        if autobattle_algo:
            cmd.extend(("--autobattle-algo", autobattle_algo))

        enemyai_algo = self.runner_config.get("enemyai_algo")
        if enemyai_algo:
            cmd.extend(("--enemyai-algo", enemyai_algo))

        seed = self.runner_config.get("seed")
        if seed:
            cmd.extend(("--seed", str(seed)))

        # Audio
        if not self.runner_config["audio"]:
            cmd.append("--no-audio")

        music_volume = self.runner_config.get("music_volume")
        if music_volume:
            cmd.extend(("--music-volume", str(music_volume)))

        sound_volume = self.runner_config.get("sound_volume")
        if sound_volume:
            cmd.extend(("--sound-volume", str(sound_volume)))

        soundfont = self.runner_config.get("soundfont")
        if soundfont:
            cmd.extend(("--soundfont", soundfont))

        # Graphics
        if self.runner_config["fullscreen"]:
            cmd.append("--fullscreen")
        else:
            cmd.append("--window")

        game_resolution = self.runner_config.get("game_resolution")
        if game_resolution:
            cmd.extend(("--game-resolution", game_resolution))

        scaling = self.runner_config.get("scaling")
        if scaling:
            cmd.extend(("--scaling", scaling))

        if self.runner_config["stretch"]:
            cmd.append("--stretch")

        if not self.runner_config["vsync"]:
            cmd.append("--no-vsync")

        fps_limit = self.runner_config.get("fps_limit")
        if fps_limit:
            cmd.extend(("--fps-limit", str(fps_limit)))

        show_fps = self.runner_config.get("show_fps")
        if show_fps != "off":
            cmd.append("--show-fps")
        if show_fps == "full":
            cmd.append("--fps-render-window")

        # Runtime Package
        if not self.runner_config["rtp"]:
            cmd.append("--no-rtp")

        return cmd

    def get_run_data(self):
        cmd = self.get_command()

        if self.default_path:
            game_path = path.expanduser(self.default_path)
            cmd.extend(("--project-path", game_path))

        return {"command": cmd, "env": self.get_env()}

    def play(self):
        if not self.game_path:
            raise GameConfigError(_("No game directory provided"))
        if not path.isdir(self.game_path):
            raise DirectoryNotFoundError(directory=self.game_path)

        cmd = self.get_command()

        cmd.extend(("--project-path", self.game_path))

        encoding = self.game_config.get("encoding")
        if encoding:
            cmd.extend(("--encoding", encoding))

        engine = self.game_config.get("engine")
        if engine:
            cmd.extend(("--engine", engine))

        patches = self.game_config.get("patches")
        if patches == "none":
            cmd.append("--no-patch")
        elif patches:
            cmd.extend(("--patches", *patches.split()))

        language = self.game_config.get("language")
        if language:
            cmd.extend(("--language", language))

        save_path = self.game_config.get("save_path")
        if save_path:
            save_path = path.expanduser(save_path)
            if not path.isdir(save_path):
                raise DirectoryNotFoundError(directory=self.game_path)
            cmd.extend(("--save-path", save_path))

        record_input = self.game_config.get("record_input")
        if record_input:
            record_input = path.expanduser(record_input)
            cmd.extend(("--record-input", record_input))

        replay_input = self.game_config.get("replay_input")
        if replay_input:
            replay_input = path.expanduser(replay_input)
            if not path.isfile(replay_input):
                raise MissingGameExecutableError(filename=replay_input)
            cmd.extend(("--replay-input", replay_input))

        load_game_id = self.game_config.get("load_game_id")
        if load_game_id:
            cmd.extend(("--load-game-id", str(load_game_id)))

        # Debug
        if self.game_config["test_play"]:
            cmd.append("--test-play")

        if self.game_config["hide_title"]:
            cmd.append("--hide-title")

        start_map_id = self.game_config.get("start_map_id")
        if start_map_id:
            cmd.extend(("--start-map-id", str(start_map_id)))

        start_position = self.game_config.get("start_position")
        if start_position:
            cmd.extend(("--start-position", *start_position.split()))

        start_party = self.game_config.get("start_party")
        if start_party:
            cmd.extend(("--start-party", *start_party.split()))

        battle_test = self.game_config.get("battle_test")
        if battle_test:
            cmd.extend(("--battle-test", battle_test))

        return {"command": cmd}
