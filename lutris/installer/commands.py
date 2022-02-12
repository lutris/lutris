"""Commands for installer scripts"""
import glob
import json
import multiprocessing
import os
import shlex
import shutil
from gettext import gettext as _
from pathlib import Path

from gi.repository import GLib

from lutris import runtime
from lutris.cache import get_cache_path
from lutris.command import MonitoredCommand
from lutris.database.games import get_game_by_field
from lutris.game import Game
from lutris.installer.errors import ScriptingError
from lutris.runners import import_task
from lutris.util import extract, linux, selective_merge, system
from lutris.util.fileio import EvilConfigParser, MultiOrderedDict
from lutris.util.log import logger
from lutris.util.wine.wine import WINE_DEFAULT_ARCH, get_wine_version_exe


class CommandsMixin:
    """The directives for the `installer:` part of the install script."""

    def __init__(self):
        if isinstance(self, CommandsMixin):
            raise RuntimeError("This class is a mixin")

    def _get_runner_version(self):
        """Return the version of the runner used for the installer"""
        if self.installer.runner == "wine":
            # If a version is specified in the script choose this one
            if self.installer.script.get(self.installer.runner):
                return self.installer.script[self.installer.runner].get("version")
            # If the installer is a extension, use the wine version from the base game
            if self.installer.requires:
                db_game = get_game_by_field(self.installer.requires, field="installer_slug")
                if not db_game:
                    db_game = get_game_by_field(self.installer.requires, field="slug")
                if not db_game:
                    logger.warning("Can't find game %s", self.installer.requires)
                    return None
                game = Game(db_game["id"])
                return game.config.runner_config["version"]
        if self.installer.runner == "libretro":
            return self.installer.script["game"]["core"]
        return None

    @staticmethod
    def _check_required_params(params, command_data, command_name):
        """Verify presence of a list of parameters required by a command."""
        if isinstance(params, str):
            params = [params]
        for param in params:
            if isinstance(param, tuple):
                param_present = False
                for key in param:
                    if key in command_data:
                        param_present = True
                if not param_present:
                    raise ScriptingError(
                        _("One of {params} parameter is mandatory for the {cmd} command").format(
                            params=_(" or ").join(param), cmd=command_name),
                        command_data,
                    )
            else:
                if param not in command_data:
                    raise ScriptingError(
                        _("The {param} parameter is mandatory for the {cmd} command").format(
                            param=param, cmd=command_name),
                        command_data,
                    )

    @staticmethod
    def _is_cached_file(file_path):
        """Return whether a file referenced by file_id is stored in the cache"""
        pga_cache_path = get_cache_path()
        if not pga_cache_path:
            return False
        return file_path.startswith(pga_cache_path)

    def chmodx(self, filename):
        """Make filename executable"""
        filename = self._substitute(filename)
        if not system.path_exists(filename):
            raise ScriptingError(_("Invalid file '%s'. Can't make it executable") % filename)
        system.make_executable(filename)

    def execute(self, data):
        """Run an executable file."""
        args = []
        terminal = None
        working_dir = None
        env = {}
        if isinstance(data, dict):
            self._check_required_params([("file", "command")], data, "execute")
            if "command" in data and "file" in data:
                raise ScriptingError(
                    _("Parameters file and command can't be used "
                      "at the same time for the execute command"),
                    data,
                )
            exec_path = data.get("file", "")
            command = data.get("command", "")
            args_string = data.get("args", "")
            for arg in shlex.split(args_string):
                args.append(self._substitute(arg))
            terminal = data.get("terminal")
            working_dir = data.get("working_dir")
            if not data.get("disable_runtime"):
                # Possibly need to handle prefer_system_libs here
                env.update(runtime.get_env())

            # Loading environment variables set in the script
            env.update(self.script_env)

            # Environment variables can also be passed to the execute command
            local_env = data.get("env") or {}
            env.update({key: self._substitute(value) for key, value in local_env.items()})
            include_processes = shlex.split(data.get("include_processes", ""))
            exclude_processes = shlex.split(data.get("exclude_processes", ""))
        elif isinstance(data, str):
            command = data
            include_processes = []
            exclude_processes = []
        else:
            raise ScriptingError(_("No parameters supplied to execute command."), data)

        if command:
            exec_path = "bash"
            args = ["-c", self._get_file_path(command.strip())]
            include_processes.append("bash")
        else:
            # Determine whether 'file' value is a file id or a path
            exec_path = self._get_file_path(exec_path)
        if system.path_exists(exec_path) and not system.is_executable(exec_path):
            logger.warning("Making %s executable", exec_path)
            system.make_executable(exec_path)
        exec_abs_path = system.find_executable(exec_path)
        if not exec_abs_path:
            raise ScriptingError(_("Unable to find executable %s") % exec_path)

        if terminal:
            terminal = linux.get_default_terminal()

        if not working_dir or not os.path.exists(working_dir):
            working_dir = self.target_path

        command = MonitoredCommand(
            [exec_abs_path] + args,
            env=env,
            term=terminal,
            cwd=working_dir,
            include_processes=include_processes,
            exclude_processes=exclude_processes,
        )
        command.start()
        GLib.idle_add(self.parent.attach_logger, command)
        self.heartbeat = GLib.timeout_add(1000, self._monitor_task, command)
        return "STOP"

    def extract(self, data):
        """Extract a file, guessing the compression method."""
        self._check_required_params([("file", "src")], data, "extract")
        src_param = data.get("file") or data.get("src")
        filespec = self._get_file_path(src_param)

        if os.path.exists(filespec):
            filenames = [filespec]
        else:
            filenames = glob.glob(filespec)

        if not filenames:
            raise ScriptingError(_("%s does not exist") % filespec)
        if "dst" in data:
            dest_path = self._substitute(data["dst"])
        else:
            dest_path = self.target_path
        for filename in filenames:
            msg = _("Extracting %s") % os.path.basename(filename)
            logger.debug(msg)
            GLib.idle_add(self.parent.set_status, msg)
            merge_single = "nomerge" not in data
            extractor = data.get("format")
            logger.debug("extracting file %s to %s", filename, dest_path)
            self._killable_process(extract.extract_archive, filename, dest_path, merge_single, extractor)
        logger.debug("Extract done")

    def input_menu(self, data):
        """Display an input request as a dropdown menu with options."""
        self._check_required_params("options", data, "input_menu")
        identifier = data.get("id")
        alias = "INPUT_%s" % identifier if identifier else None
        has_entry = data.get("entry")
        options = data["options"]
        preselect = self._substitute(data.get("preselect", ""))
        GLib.idle_add(
            self.parent.input_menu,
            alias,
            options,
            preselect,
            has_entry,
            self._on_input_menu_validated,
        )
        return "STOP"

    def _on_input_menu_validated(self, _widget, *args):
        alias = args[0]
        menu = args[1]
        choosen_option = menu.get_active_id()
        if choosen_option:
            self.user_inputs.append({"alias": alias, "value": choosen_option})
            GLib.idle_add(self.parent.continue_button.hide)
            self._iter_commands()

    def insert_disc(self, data):
        """Request user to insert an optical disc"""
        self._check_required_params("requires", data, "insert_disc")
        requires = data.get("requires")
        message = data.get(
            "message",
            _("Insert or mount game disc and click Autodetect or\n"
              "use Browse if the disc is mounted on a non standard location."),
        )
        message += (
            _("\n\nLutris is looking for a mounted disk drive or image \n"
              "containing the following file or folder:\n"
              "<i>%s</i>") % requires
        )
        if self.installer.runner == "wine":
            GLib.idle_add(self.parent.eject_button.show)
        GLib.idle_add(self.parent.ask_for_disc, message, self._find_matching_disc, requires)
        return "STOP"

    def _find_matching_disc(self, _widget, requires, extra_path=None):
        if extra_path:
            drives = [extra_path]
        else:
            drives = system.get_mounted_discs()
        for drive in drives:
            required_abspath = os.path.join(drive, requires)
            required_abspath = system.fix_path_case(required_abspath)
            if required_abspath and system.path_exists(required_abspath):
                logger.debug("Found %s on cdrom %s", requires, drive)
                self.game_disc = drive
                self._iter_commands()
                break

    def mkdir(self, directory):
        """Create directory"""
        directory = self._substitute(directory)
        try:
            os.makedirs(directory)
        except OSError:
            logger.debug("Directory %s already exists", directory)
        else:
            logger.debug("Created directory %s", directory)

    def merge(self, params):
        """Merge the contents given by src to destination folder dst"""
        self._check_required_params(["src", "dst"], params, "merge")
        src, dst = self._get_move_paths(params)
        logger.debug("Merging %s into %s", src, dst)
        if not os.path.exists(src):
            if params.get("optional"):
                logger.info("Optional path %s not present", src)
                return
            raise ScriptingError(_("Source does not exist: %s") % src, params)
        os.makedirs(dst, exist_ok=True)
        if os.path.isfile(src):
            # If single file, copy it and change reference in game file so it
            # can be used as executable. Skip copying if the source is the same
            # as destination.
            if os.path.dirname(src) != dst:
                self._killable_process(shutil.copy, src, dst)
            if params["src"] in self.game_files.keys():
                self.game_files[params["src"]] = os.path.join(dst, os.path.basename(src))
            return
        self._killable_process(system.merge_folders, src, dst)

    def copy(self, params):
        """Alias for merge"""
        self.merge(params)

    def move(self, params):
        """Move a file or directory into a destination folder."""
        self._check_required_params(["src", "dst"], params, "move")
        src, dst = self._get_move_paths(params)
        logger.debug("Moving %s to %s", src, dst)
        if not os.path.exists(src):
            if params.get("optional"):
                logger.info("Optional path %s not present", src)
                return
            raise ScriptingError(_("Invalid source for 'move' operation: %s") % src)

        if os.path.isfile(src):
            if os.path.dirname(src) == dst:
                logger.info("Source file is the same as destination, skipping")
                return

            if os.path.exists(os.path.join(dst, os.path.basename(src))):
                # May not be the best choice, but it's the safest.
                # Maybe should display confirmation dialog (Overwrite / Skip) ?
                logger.info("Destination file exists, skipping")
                return
        try:
            if self._is_cached_file(src):
                action = shutil.copy
            else:
                action = shutil.move
            self._killable_process(action, src, dst)
        except shutil.Error as err:
            raise ScriptingError(_("Can't move {src} \nto destination {dst}").format(src=src, dst=dst)) from err

    def rename(self, params):
        """Rename file or folder."""
        self._check_required_params(["src", "dst"], params, "rename")
        src, dst = self._get_move_paths(params)
        if not os.path.exists(src):
            raise ScriptingError(_("Rename error, source path does not exist: %s") % src)
        if os.path.isdir(dst):
            try:
                os.rmdir(dst)  # Remove if empty
            except OSError:
                pass
        if os.path.exists(dst):
            raise ScriptingError(_("Rename error, destination already exists: %s") % src)
        dst_dir = os.path.dirname(dst)

        # Pre-move on dest filesystem to avoid error with
        # os.rename through different filesystems
        temp_dir = os.path.join(dst_dir, "lutris_rename_temp")
        os.makedirs(temp_dir)
        self._killable_process(shutil.move, src, temp_dir)
        src = os.path.join(temp_dir, os.path.basename(src))
        os.renames(src, dst)

    def _get_move_paths(self, params):
        """Process raw 'src' and 'dst' data."""
        try:
            src_ref = params["src"]
        except KeyError as err:
            raise ScriptingError(_("Missing parameter src")) from err
        src = self.game_files.get(src_ref) or self._substitute(src_ref)
        if not src:
            raise ScriptingError(_("Wrong value for 'src' param"), src_ref)
        dst_ref = params["dst"]
        dst = self._substitute(dst_ref)
        if not dst:
            raise ScriptingError(_("Wrong value for 'dst' param"), dst_ref)
        return src.rstrip("/"), dst.rstrip("/")

    def substitute_vars(self, data):
        """Subsitute variable names found in given file."""
        self._check_required_params("file", data, "substitute_vars")
        filename = self._substitute(data["file"])
        logger.debug("Substituting variables for file %s", filename)
        tmp_filename = filename + ".tmp"
        with open(filename, "r", encoding='utf-8') as source_file:
            with open(tmp_filename, "w", encoding='utf-8') as dest_file:
                line = "."
                while line:
                    line = source_file.readline()
                    line = self._substitute(line)
                    dest_file.write(line)
        os.rename(tmp_filename, filename)

    def _get_task_runner_and_name(self, task_name):
        if "." in task_name:
            # Run a task from a different runner
            # than the one for this installer
            runner_name, task_name = task_name.split(".")
        else:
            runner_name = self.installer.runner
        return runner_name, task_name

    def get_wine_path(self):
        """Return absolute path of wine version used during the install"""
        return get_wine_version_exe(self._get_runner_version())

    def task(self, data):
        """Directive triggering another function specific to a runner.

        The 'name' parameter is mandatory. If 'args' is provided it will be
        passed to the runner task.
        """
        self._check_required_params("name", data, "task")
        if self.parent:
            GLib.idle_add(self.parent.cancel_button.set_sensitive, False)
        runner_name, task_name = self._get_task_runner_and_name(data.pop("name"))

        if runner_name.startswith("wine"):
            wine_path = self.get_wine_path()
            if wine_path:
                data["wine_path"] = wine_path
            data["prefix"] = data.get("prefix") \
                or self.installer.script.get("game", {}).get("prefix") \
                or "$GAMEDIR"
            data["arch"] = data.get("arch") \
                or self.installer.script.get("game", {}).get("arch") \
                or WINE_DEFAULT_ARCH
            if task_name == "wineexec":
                data["env"] = self.script_env

        for key in data:
            value = data[key]
            if isinstance(value, dict):
                for inner_key in value:
                    value[inner_key] = self._substitute(value[inner_key])
            elif isinstance(value, list):
                for index, elem in enumerate(value):
                    value[index] = self._substitute(elem)
            else:
                value = self._substitute(data[key])
            data[key] = value

        task = import_task(runner_name, task_name)
        command = task(**data)
        GLib.idle_add(self.parent.cancel_button.set_sensitive, True)
        if isinstance(command, MonitoredCommand):
            # Monitor thread and continue when task has executed
            GLib.idle_add(self.parent.attach_logger, command)
            self.heartbeat = GLib.timeout_add(1000, self._monitor_task, command)
            return "STOP"
        return None

    def _monitor_task(self, command):
        if not command.is_running:
            logger.debug("Return code: %s", command.return_code)
            if command.return_code != "0":
                raise ScriptingError(_("Command exited with code %s") % command.return_code)
            self._iter_commands()
            return False
        return True

    def write_file(self, params):
        """Write text to a file."""
        self._check_required_params(["file", "content"], params, "write_file")

        # Get file
        dest_file_path = self._get_file_path(params["file"])

        # Create dir if necessary
        basedir = os.path.dirname(dest_file_path)
        os.makedirs(basedir, exist_ok=True)

        mode = params.get("mode", "w")
        if not mode.startswith(("a", "w")):
            raise ScriptingError(_("Wrong value for write_file mode: '%s'") % mode)

        with open(dest_file_path, mode, encoding='utf-8') as dest_file:
            dest_file.write(self._substitute(params["content"]))

    def write_json(self, params):
        """Write data into a json file."""
        self._check_required_params(["file", "data"], params, "write_json")

        # Get file
        filename = self._get_file_path(params["file"])

        # Create dir if necessary
        basedir = os.path.dirname(filename)
        os.makedirs(basedir, exist_ok=True)

        merge = params.get("merge", True)

        # create an empty file if it doesn't exist
        Path(filename).touch(exist_ok=True)

        with open(filename, "r+" if merge else "w", encoding='utf-8') as json_file:
            json_data = {}
            if merge:
                try:
                    json_data = json.load(json_file)
                except ValueError:
                    logger.error("Failed to parse JSON from file %s", filename)

            json_data = selective_merge(json_data, params.get("data", {}))
            json_file.seek(0)
            json_file.write(json.dumps(json_data, indent=2))

    def write_config(self, params):
        """Write a key-value pair into an INI type config file."""
        if params.get("data"):
            self._check_required_params(["file", "data"], params, "write_config")
        else:
            self._check_required_params(["file", "section", "key", "value"], params, "write_config")
        # Get file
        config_file_path = self._get_file_path(params["file"])

        # Create dir if necessary
        basedir = os.path.dirname(config_file_path)
        os.makedirs(basedir, exist_ok=True)

        merge = params.get("merge", True)

        parser = EvilConfigParser(allow_no_value=True, dict_type=MultiOrderedDict, strict=False)
        parser.optionxform = str  # Preserve text case
        if merge:
            parser.read(config_file_path)

        data = {}
        if params.get("data"):
            data = params["data"]
        else:
            data[params["section"]] = {}
            data[params["section"]][params["key"]] = params["value"]

        for section, keys in data.items():
            if not parser.has_section(section):
                parser.add_section(section)
            for key, value in keys.items():
                value = self._substitute(value)
                parser.set(section, key, value)

        with open(config_file_path, "wb") as config_file:
            parser.write(config_file)

    def _get_file_path(self, fileid):
        file_path = self.game_files.get(fileid)
        if not file_path:
            file_path = self._substitute(fileid)
        return file_path

    def _killable_process(self, func, *args, **kwargs):
        """Run function `func` in a separate, killable process."""
        with multiprocessing.Pool(1) as process:
            result_obj = process.apply_async(func, args, kwargs)
            self.abort_current_task = process.terminate
            result = result_obj.get()  # Wait process end & re-raise exceptions
            self.abort_current_task = None
            logger.debug("Process %s returned: %s", func, result)
            return result

    def _extract_gog_game(self, file_id):
        self.extract({
            "src": file_id,
            "dst": "$GAMEDIR",
            "extractor": "innoextract"
        })
        app_path = os.path.join(self.target_path, "app")
        if system.path_exists(app_path):
            for app_content in os.listdir(app_path):
                source_path = os.path.join(app_path, app_content)
                if os.path.exists(os.path.join(self.target_path, app_content)):
                    self.merge({"src": source_path, "dst": self.target_path})
                else:
                    self.move({"src": source_path, "dst": self.target_path})
        support_path = os.path.join(self.target_path, "__support/app")
        if system.path_exists(support_path):
            self.merge({"src": support_path, "dst": self.target_path})

    def _get_scummvm_arguments(self, gog_config_path):
        """Return a ScummVM configuration from the GOG config files"""
        with open(gog_config_path, encoding='utf-8') as gog_config_file:
            gog_config = json.loads(gog_config_file.read())
        game_tasks = [task for task in gog_config["playTasks"] if task["category"] == "game"]
        arguments = game_tasks[0]["arguments"]
        game_id = arguments.split()[-1]
        arguments = " ".join(arguments.split()[:-1])
        base_dir = os.path.dirname(gog_config_path)
        return {
            "game_id": game_id,
            "path": base_dir,
            "arguments": arguments
        }

    def autosetup_gog_game(self, file_id, silent=False):
        """Automatically guess the best way to install a GOG game by inspecting its contents.
        This chooses the right runner (DOSBox, Wine) for Windows game files.
        Linux setup files don't use innosetup, they can be unzipped instead.
        """
        file_path = self.game_files[file_id]
        file_list = extract.get_innoextract_list(file_path)
        dosbox_found = False
        scummvm_found = False
        windows_override_found = False  # DOS games that also have a Windows executable
        for filename in file_list:
            if "dosbox/dosbox.exe" in filename.lower():
                dosbox_found = True
            if "scummvm/scummvm.exe" in filename.lower():
                scummvm_found = True
            if "_some_windows.exe" in filename.lower():
                # There's not a good way to handle exceptions without extracting the .info file
                # before extracting the game. Added for Quake but GlQuake.exe doesn't run on modern wine
                windows_override_found = True
        if dosbox_found and not windows_override_found:
            self._extract_gog_game(file_id)
            dosbox_config = {
                "working_dir": "$GAMEDIR/DOSBOX",
            }
            for filename in os.listdir(self.target_path):
                if filename.endswith("_single.conf"):
                    dosbox_config["main_file"] = filename
                elif filename.endswith(".conf"):
                    dosbox_config["config_file"] = filename
            self.installer.script["game"] = dosbox_config
            self.installer.runner = "dosbox"
        elif scummvm_found:
            self._extract_gog_game(file_id)
            arguments = None
            for filename in os.listdir(self.target_path):
                if filename.startswith("goggame") and filename.endswith(".info"):
                    arguments = self._get_scummvm_arguments(os.path.join(self.target_path, filename))
            if not arguments:
                raise RuntimeError("Unable to get ScummVM arguments")
            logger.info("ScummVM config: %s", arguments)
            self.installer.script["game"] = arguments
            self.installer.runner = "scummvm"
        else:
            args = "/SP- /NOCANCEL"
            if silent:
                args += " /SUPPRESSMSGBOXES /VERYSILENT /NOGUI"
            self.installer.is_gog = True
            return self.task({
                "name": "wineexec",
                "prefix": "$GAMEDIR",
                "executable": file_id,
                "args": args
            })
