"""Commands for installer scripts"""

import glob
import json
import multiprocessing
import os
import shlex
import shutil
from gettext import gettext as _
from pathlib import Path

from lutris import runtime, settings
from lutris.cache import is_file_in_custom_cache
from lutris.exceptions import MissingExecutableError, UnspecifiedVersionError
from lutris.installer.errors import ScriptingError
from lutris.installer.installer import LutrisInstaller
from lutris.monitored_command import MonitoredCommand
from lutris.runners import InvalidRunnerError, import_runner, import_task
from lutris.runners.wine import wine
from lutris.util import extract, linux, selective_merge, system
from lutris.util.fileio import EvilConfigParser, MultiOrderedDict
from lutris.util.gog import apply_gog_config
from lutris.util.gogdl import run_gogdl
from lutris.util.jobs import schedule_repeating_at_idle
from lutris.util.log import logger
from lutris.util.wine.wine import WINE_DEFAULT_ARCH, get_default_wine_version, get_wine_path_for_version


class CommandsMixin:
    """The directives for the `installer:` part of the install script."""

    # pylint: disable=no-member
    installer: LutrisInstaller = NotImplemented

    def get_wine_path(self) -> str:
        """Return absolute path of wine version used during the installation, but
        None if the wine exe can't be located."""
        runner = self.get_runner_class(self.installer.runner)()
        version = runner.get_installer_runner_version(self.installer, use_runner_config=False)
        if version:
            wine_path = get_wine_path_for_version(version)
            return wine_path

        # Special case that lets the Wine configuration explicit specify the path
        # to the Wine executable, not just a version number.
        if self.installer.runner == "wine":
            try:
                config_version, runner_config = wine.get_runner_version_and_config()
                wine_path = get_wine_path_for_version(config_version, config=runner_config.runner_level["wine"])
                return wine_path
            except UnspecifiedVersionError:
                pass

        version = get_default_wine_version()
        wine_path = get_wine_path_for_version(version)
        return wine_path

    def get_runner_class(self, runner_name):
        """Runner the runner class from its name"""
        try:
            runner = import_runner(runner_name)
        except InvalidRunnerError as err:
            raise ScriptingError(_("Invalid runner provided %s") % runner_name) from err
        return runner

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
                            params=_(" or ").join(param), cmd=command_name
                        ),
                        faulty_data=command_data,
                    )
            else:
                if param not in command_data:
                    raise ScriptingError(
                        _("The {param} parameter is mandatory for the {cmd} command").format(
                            param=param, cmd=command_name
                        ),
                        faulty_data=command_data,
                    )

    def chmodx(self, filename):
        """Make filename executable"""
        filename = self._substitute(filename)
        self._check_path_within_target(filename, "chmodx")
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
                    _("Parameters file and command can't be used at the same time for the execute command"),
                    faulty_data=data,
                )

            # Accept return codes other than 0
            if "return_code" in data:
                return_code = data.pop("return_code")
            else:
                return_code = "0"

            exec_path = data.get("file", "")
            command = data.get("command", "")
            args_string = data.get("args", "")
            for arg in shlex.split(args_string):
                args.append(self._substitute(arg))
            terminal = data.get("terminal")
            working_dir = data.get("working_dir")
            if working_dir:
                working_dir = self._substitute(working_dir)
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
            raise ScriptingError(_("No parameters supplied to execute command."), faulty_data=data)

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

        try:
            exec_abs_path = system.find_required_executable(exec_path)
        except MissingExecutableError as ex:
            raise ScriptingError(_("Unable to find executable %s") % exec_path) from ex

        if terminal:
            terminal = linux.get_default_terminal()
        if working_dir and not os.path.isdir(working_dir):
            logger.warning(
                "Working directory %s doesn't exist or is not a directory, using target path instead", working_dir
            )
            working_dir = None
        if not working_dir:
            working_dir = self.target_path

        command = MonitoredCommand(
            [exec_abs_path] + args,
            env=env,
            term=terminal,
            cwd=working_dir,
            include_processes=include_processes,
            exclude_processes=exclude_processes,
        )
        command.accepted_return_code = return_code
        command.start()
        self.interpreter_ui_delegate.attach_log(command)
        schedule_repeating_at_idle(self._monitor_task, command, interval_seconds=1.0)
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
            self._check_path_within_target(dest_path, "extract")
        else:
            dest_path = self.target_path
        for filename in filenames:
            msg = _("Extracting %s") % os.path.basename(filename)
            logger.debug(msg)
            self.interpreter_ui_delegate.report_status(msg)
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
        options = data["options"]
        preselect = self._substitute(data.get("preselect", ""))
        self.interpreter_ui_delegate.begin_input_menu(alias, options, preselect, self._on_input_menu_validated)
        return "STOP"

    def _on_input_menu_validated(self, alias, menu):
        choosen_option = menu.get_active_id()
        if choosen_option:
            self.user_inputs.append({"alias": alias, "value": choosen_option})
            self._iter_commands()
        else:
            raise RuntimeError("A required input option was not selected, so the installation can't continue.")

    def insert_disc(self, data):
        """Request user to insert an optical disc"""
        self._check_required_params("requires", data, "insert_disc")
        requires = data.get("requires")
        message = data.get(
            "message",
            _(
                "Insert or mount game disc and click Autodetect or\n"
                "use Browse if the disc is mounted on a non standard location."
            ),
        )
        message += (
            _(
                "\n\nLutris is looking for a mounted disk drive or image \n"
                "containing the following file or folder:\n"
                "<i>%s</i>"
            )
            % requires
        )
        self.interpreter_ui_delegate.begin_disc_prompt(message, requires, self.installer, self._find_matching_disc)
        return "STOP"

    def _find_matching_disc(self, _widget, requires, extra_path=None):
        if extra_path:
            drives = [extra_path]
        else:
            drives = system.get_mounted_discs()
        for drive in drives:
            required_abspath = os.path.join(drive, requires)
            required_abspath = system.fix_path_case(required_abspath)
            if system.path_exists(required_abspath):
                logger.debug("Found %s on cdrom %s", requires, drive)
                self.game_disc = drive
                self._iter_commands()
                return

        raise RuntimeError(_("The required file '%s' could not be located.") % requires)

    def mkdir(self, directory):
        """Create directory"""
        directory = self._substitute(directory)
        self._check_path_within_target(directory, "mkdir")
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
            if is_file_in_custom_cache(src):
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
        self._check_path_within_target(dst, "move/merge/rename")
        return src.rstrip("/"), dst.rstrip("/")

    def substitute_vars(self, data):
        """Substitute variable names found in given file."""
        self._check_required_params("file", data, "substitute_vars")
        filename = self._substitute(data["file"])
        self._check_path_within_target(filename, "substitute_vars")
        logger.debug("Substituting variables for file %s", filename)
        tmp_filename = filename + ".tmp"
        with open(filename, "r", encoding="utf-8") as source_file:
            with open(tmp_filename, "w", encoding="utf-8") as dest_file:
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

        task_name = task_name.replace("-", "_")
        # Prevent private functions from being accessed as commands
        task_name = task_name.strip("_")
        return runner_name, task_name

    def task(self, data):
        """Directive triggering another function specific to a runner.

        The 'name' parameter is mandatory. If 'args' is provided it will be
        passed to the runner task.
        """
        self._check_required_params("name", data, "task")
        runner_name, task_name = self._get_task_runner_and_name(data.pop("name"))

        # Accept return codes other than 0
        if "return_code" in data:
            return_code = data.pop("return_code")
        else:
            return_code = "0"

        if runner_name.startswith("wine"):
            data["wine_path"] = self.get_wine_path()
            data["prefix"] = data.get("prefix") or self.installer.script.get("game", {}).get("prefix") or "$GAMEDIR"
            data["arch"] = data.get("arch") or self.installer.script.get("game", {}).get("arch") or WINE_DEFAULT_ARCH
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
        if isinstance(command, MonitoredCommand):
            # Monitor thread and continue when task has executed
            self.interpreter_ui_delegate.attach_log(command)
            command.accepted_return_code = return_code
            schedule_repeating_at_idle(self._monitor_task, command, interval_seconds=1.0)
            return "STOP"
        return None

    def _monitor_task(self, command):
        if not command.is_running:
            logger.debug("Return code: %s", command.return_code)
            if command.return_code not in (str(command.accepted_return_code), "0"):
                raise ScriptingError(_("Command exited with code %s") % command.return_code)

            self._iter_commands()
            return False
        return True  # keep checking

    def write_file(self, params):
        """Write text to a file."""
        self._check_required_params(["file", "content"], params, "write_file")

        # Get file
        dest_file_path = self._get_file_path(params["file"])
        self._check_path_within_target(dest_file_path, "write_file")

        # Create dir if necessary
        basedir = os.path.dirname(dest_file_path)
        os.makedirs(basedir, exist_ok=True)

        mode = params.get("mode", "w")
        if not mode.startswith(("a", "w")):
            raise ScriptingError(_("Wrong value for write_file mode: '%s'") % mode)

        with open(dest_file_path, mode, encoding="utf-8") as dest_file:
            dest_file.write(self._substitute(params["content"]))

    def write_json(self, params):
        """Write data into a json file."""
        self._check_required_params(["file", "data"], params, "write_json")

        # Get file
        filename = self._get_file_path(params["file"])
        self._check_path_within_target(filename, "write_json")

        # Create dir if necessary
        basedir = os.path.dirname(filename)
        os.makedirs(basedir, exist_ok=True)

        merge = params.get("merge", True)

        # create an empty file if it doesn't exist
        Path(filename).touch(exist_ok=True)

        with open(filename, "r+" if merge else "w", encoding="utf-8") as json_file:
            json_data = {}
            if merge:
                try:
                    json_data = json.load(json_file)
                except ValueError:
                    logger.error("Failed to parse JSON from file %s", filename)

            json_data = selective_merge(json_data, params.get("data", {}))
            json_file.seek(0)
            json_file.truncate()
            json_file.write(json.dumps(json_data, indent=2))

    def write_config(self, params):
        """Write a key-value pair into an INI type config file."""
        if params.get("data"):
            self._check_required_params(["file", "data"], params, "write_config")
        else:
            self._check_required_params(["file", "section", "key", "value"], params, "write_config")
        # Get file
        config_file_path = self._get_file_path(params["file"])
        self._check_path_within_target(config_file_path, "write_config")

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

    def _extract_innosetup(self, file_id):
        self.extract({"src": file_id, "dst": "$GAMEDIR", "extractor": "innoextract"})
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
        with open(gog_config_path, encoding="utf-8") as gog_config_file:
            gog_config = json.loads(gog_config_file.read())
        game_tasks = [task for task in gog_config["playTasks"] if task["category"] == "game"]
        arguments = game_tasks[0]["arguments"]
        game_id = arguments.split()[-1]
        arguments = " ".join(arguments.split()[:-1])
        base_dir = os.path.dirname(gog_config_path)
        return {"game_id": game_id, "path": base_dir, "args": arguments}

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
            if "dosbox.exe" in filename.casefold():
                dosbox_found = True
            if "scummvm.exe" in filename.casefold():
                scummvm_found = True
            if "_some_windows.exe" in filename.casefold():
                # There's not a good way to handle exceptions without extracting the .info file
                # before extracting the game. Added for Quake but GlQuake.exe doesn't run on modern wine
                windows_override_found = True
        if dosbox_found and not windows_override_found:
            self._extract_innosetup(file_id)
            if "DOSBOX" in os.listdir(self.target_path):
                dosbox_config = {
                    "working_dir": "$GAMEDIR/DOSBOX",
                }
            else:
                dosbox_config = {}
            single_conf = None
            config_file = None
            for filename in os.listdir(self.target_path):
                if filename == "dosbox.conf":
                    dosbox_config["main_file"] = filename
                elif filename.endswith("_single.conf"):
                    single_conf = filename
                elif filename.endswith(".conf"):
                    config_file = filename
            if single_conf:
                dosbox_config["main_file"] = single_conf
            if config_file:
                if dosbox_config.get("main_file"):
                    dosbox_config["config_file"] = config_file
                else:
                    dosbox_config["main_file"] = config_file
            self.installer.script["game"] = dosbox_config
            self.installer.runner = "dosbox"
        elif scummvm_found:
            self._extract_innosetup(file_id)
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
            self.installer.post_install_hooks.append(apply_gog_config)
            return self.task({"name": "wineexec", "prefix": "$GAMEDIR", "executable": file_id, "args": args})

    def _get_dosbox_arguments(self, zoom_bat_path):
        """Return the arguments for the DOSBox executable from a ZOOM Plaform installer"""
        with open(zoom_bat_path, encoding="utf-8") as zoom_bat_file:
            zoom_bat = zoom_bat_file.read()

        # Find the line that starts with ".\DOSBOX\dosbox.exe" and extract the arguments
        lines = zoom_bat.splitlines()
        arguments = []
        for line in lines:
            if line.startswith(".\\DOSBOX\\dosbox.exe"):
                # Extract the arguments from the line
                arguments = line.split(" ", 1)[1].strip()
                break

        return arguments

    def autosetup_zoom_platform(self, file_id, silent=False):
        """Automatically guess the best way to install a ZOOM Platofrm game by inspecting its contents.
        This chooses the right runner (DOSBox, Wine) for Windows game files.
        Linux setup files don't use innosetup, they can be unzipped instead.
        """
        file_path = self.game_files[file_id]
        file_list = extract.get_innoextract_list(file_path)
        dosbox_found = False
        scummvm_found = False
        for filename in file_list:
            if "dosbox.exe" in filename.casefold():
                dosbox_found = True
            if "scummvm.exe" in filename.casefold():
                scummvm_found = True
        if dosbox_found:
            self._extract_innosetup(file_id)
            dosbox_config = {}
            single_conf = None
            config_file = None
            for filename in os.listdir(self.target_path):
                if filename == "dosbox.conf":
                    dosbox_config["main_file"] = filename
                elif filename.endswith("_single.conf"):
                    single_conf = filename
                elif filename.endswith(".conf"):
                    config_file = filename
            if single_conf:
                dosbox_config["main_file"] = single_conf
            if config_file:
                if dosbox_config.get("main_file"):
                    dosbox_config["config_file"] = config_file
                else:
                    dosbox_config["main_file"] = config_file

            for filename in os.listdir(self.target_path):
                if filename.startswith("Launch") and filename.endswith(".bat"):
                    arguments = self._get_dosbox_arguments(os.path.join(self.target_path, filename))

            if len(arguments) > 0:
                # Add the arguments to the dosbox config
                dosbox_config["args"] = arguments
                # Remove "config_file" from the dosbox config
                dosbox_config.pop("config_file", None)

            self.installer.script["game"] = dosbox_config
            self.installer.runner = "dosbox"
        elif scummvm_found:
            self._extract_innoextract_setup(file_id)
            arguments = {"path": os.path.join(self.target_path, "Data"), "args": "--auto-detect"}
            logger.info("ScummVM config: %s", arguments)
            self.installer.script["game"] = arguments
            self.installer.runner = "scummvm"
        else:
            args = "/SP- /NOCANCEL"
            if silent:
                args += " /SUPPRESSMSGBOXES /VERYSILENT /NOGUI"
            return self.task({"name": "wineexec", "prefix": "$GAMEDIR", "executable": file_id, "args": args})

    def autosetup_amazon(self, file_and_dir_dict):
        files = file_and_dir_dict["files"]
        directories = file_and_dir_dict["directories"]

        # create directories
        for directory in directories:
            self.mkdir(f"$GAMEDIR/drive_c/game/{directory}")

        # move installed files from CACHE to game folder
        for file_hash, file_data in files.items():
            if file_hash not in self.game_files:
                logger.warning("Amazon: Missing file hash %s (expected at %s)", file_hash, file_data["paths"][0])
                continue

            source_file = self.game_files[file_hash]
            paths = file_data["paths"]

            for path in paths:
                dest_path = f"$GAMEDIR/drive_c/game/{path}"

                abs_dest_path = self._substitute(dest_path)
                if os.path.isdir(abs_dest_path):
                    logger.warning("Amazon: Removing conflicting directory %s", abs_dest_path)
                    shutil.rmtree(abs_dest_path)

                self._killable_process(shutil.copyfile, source_file, abs_dest_path)

            if os.path.exists(source_file):
                os.remove(source_file)

    def gogdl_setup(self, data):
        """Download and set up a GOG game via depot/CDN using heroic-gogdl.

        Params:
            game_id: GOG product ID
            platform: "windows" or "linux" (default: based on runner)
            lang: language code (default: system locale)
            dlcs: "all", "none", or comma-separated DLC IDs (optional)
            command: "download" | "update" | "repair" (default: "download")
        """
        self._check_required_params("game_id", data, "gogdl_setup")

        game_id = str(data["game_id"])
        command = data.get("command", "download")
        platform = data.get("platform")
        lang = data.get("lang")
        dlcs_param = data.get("dlcs")

        if not platform:
            platform = "linux" if self.installer.runner == "linux" else "windows"

        # Determine install path
        # gogdl appends the game's installDirectory (from the depot manifest)
        # to the path on fresh downloads, so we point it at the parent only.
        install_path = self.target_path

        os.makedirs(install_path, exist_ok=True)

        # Handle DLC parameter
        if dlcs_param == "all":
            dlcs = True
        elif dlcs_param == "none":
            dlcs = False
        elif dlcs_param:
            dlcs = str(dlcs_param)
        else:
            dlcs = None

        # Clear stale manifest for fresh downloads so gogdl doesn't
        # think the game is already installed from a previous attempt.
        if command == "download":
            manifest_path = os.path.join(settings.CACHE_DIR, "gogdl", "heroic_gogdl", "manifests", game_id)
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
                logger.debug("Cleared stale gogdl manifest for %s", game_id)

        msg = _("Downloading via GOG depot...")
        logger.info(msg)
        self.interpreter_ui_delegate.report_status(msg)

        def progress_callback(progress):
            fraction = progress.percent / 100.0
            parts = []
            if progress.speed_mib > 0:
                parts.append(_("{speed:.1f} MiB/s").format(speed=progress.speed_mib))
            if progress.eta and progress.eta != "00:00:00":
                parts.append(_("ETA: {eta}").format(eta=progress.eta))
            text = " — ".join(parts) if parts else ""
            self.interpreter_ui_delegate.report_progress(fraction, text)

        try:
            run_gogdl(
                command=command,
                game_id=game_id,
                path=install_path,
                platform=platform,
                lang=lang,
                dlcs=dlcs,
                progress_callback=progress_callback,
            )
        except FileNotFoundError as err:
            raise ScriptingError(_("gogdl runtime component not found. Please update your Lutris runtime.")) from err
        except Exception as err:
            raise ScriptingError(_("GOG depot download failed: %s") % err) from err

        self.interpreter_ui_delegate.report_progress(None)

        # Post-install: find where gogdl actually put the files and apply config.
        # For "download", gogdl appends installDirectory to the path, so we
        # need to discover the actual game directory.
        if command == "download":
            game_path = self._find_gogdl_game_path(install_path)
        else:
            game_path = install_path

        self._apply_gogdl_post_install(game_path, platform)
        logger.info("GOG depot download completed for %s", game_id)

    def _find_gogdl_game_path(self, parent_path):
        """Find the actual game directory under parent_path after a gogdl download.
        gogdl creates a subdirectory named after the game's installDirectory."""
        if not os.path.isdir(parent_path):
            return parent_path
        entries = [e for e in os.listdir(parent_path) if os.path.isdir(os.path.join(parent_path, e))]
        if len(entries) == 1:
            return os.path.join(parent_path, entries[0])
        # Multiple dirs or none — look for goggame-*.info to find the right one
        for entry in entries:
            candidate = os.path.join(parent_path, entry)
            if any(f.startswith("goggame") and f.endswith(".info") for f in os.listdir(candidate)):
                return candidate
        return parent_path

    def _find_gog_config_path(self, install_path):
        """Find the directory containing goggame-*.info, searching subdirectories.

        Linux GOG games nest the info file under a 'game/' subdirectory,
        while Windows games place it directly in the install path."""
        matches = glob.glob(os.path.join(install_path, "**/goggame-*.info"), recursive=True)
        if matches:
            return os.path.dirname(matches[0])
        return install_path

    def _apply_gogdl_post_install(self, install_path, platform):
        """Detect game configuration from goggame-*.info after a depot download."""
        from lutris.util.gog import convert_gog_config_to_lutris, get_gog_config

        config_path = self._find_gog_config_path(install_path)
        if not config_path:
            return

        gog_config = get_gog_config(config_path)
        if not gog_config:
            return

        play_tasks = gog_config.get("playTasks", [])
        if not play_tasks:
            return

        # Detect DOSBox/ScummVM games from playTasks
        for task in play_tasks:
            task_path = task.get("path", "").casefold()
            if "dosbox" in task_path:
                self._configure_dosbox_from_depot(install_path, gog_config)
                return
            if "scummvm" in task_path:
                self._configure_scummvm_from_depot(install_path, gog_config)
                return

        # Normal game — apply config from goggame-*.info
        lutris_config = convert_gog_config_to_lutris(gog_config, config_path)
        if lutris_config and "game" in self.installer.script:
            # For Linux GOG games, prefer start.sh over the binary from goggame info.
            # GOG's start.sh handles working directory setup and permissions.
            if platform == "linux":
                start_sh = os.path.join(install_path, "start.sh")
                if os.path.isfile(start_sh):
                    lutris_config["exe"] = start_sh
                    system.make_executable(start_sh)
            self.installer.script["game"].update(lutris_config)

    def _configure_dosbox_from_depot(self, install_path, gog_config):
        """Configure a DOSBox game from depot download using playTasks args.

        In depot layouts, the -conf paths in goggame-*.info are relative to
        the GOG Galaxy working dir and may not resolve directly. The actual
        conf files are typically in gog-support/{id}/app/. We parse the
        conf filenames from the arguments and search the install tree for them.
        """
        game_task = next(
            (t for t in gog_config.get("playTasks", []) if t.get("category") == "game"),
            None,
        )
        if not game_task:
            logger.warning("No game playTask found in goggame info for DOSBox game")
            return

        arguments = game_task.get("arguments", "")

        # Parse -conf arguments to get the config filenames
        try:
            args = shlex.split(arguments)
        except ValueError:
            args = arguments.split()

        conf_names = []
        i = 0
        while i < len(args):
            if args[i] == "-conf" and i + 1 < len(args):
                conf_name = os.path.basename(args[i + 1].replace("\\", "/"))
                conf_names.append(conf_name)
                i += 2
            else:
                i += 1

        # Search install tree for the actual conf files
        conf_files = []
        for conf_name in conf_names:
            for dirpath, _dirnames, filenames in os.walk(install_path):
                if conf_name in filenames:
                    conf_files.append(os.path.join(dirpath, conf_name))
                    break

        dosbox_config = {}

        if conf_files:
            single = next((c for c in conf_files if "_single" in c), None)
            dosbox_config["main_file"] = single or conf_files[0]
            remaining = [c for c in conf_files if c != dosbox_config["main_file"]]
            if remaining:
                dosbox_config["config_file"] = remaining[0]

        self.installer.script["game"] = dosbox_config
        self.installer.runner = "dosbox"

    def _configure_scummvm_from_depot(self, install_path, gog_config):
        """Configure a ScummVM game from depot download using playTasks args."""
        game_task = next(
            (t for t in gog_config.get("playTasks", []) if t.get("category") == "game"),
            None,
        )
        if not game_task:
            return
        arguments = game_task.get("arguments", "")
        parts = arguments.split()
        if parts:
            game_id = parts[-1]
            args = " ".join(parts[:-1])
            self.installer.script["game"] = {
                "game_id": game_id,
                "path": install_path,
                "args": args,
            }
            self.installer.runner = "scummvm"

    def install_or_extract(self, file_id):
        """Runs if file is executable or extracts if file is archive"""
        file_path = self._get_file_path(file_id)
        runner = self.installer.runner
        if runner != "wine":
            raise ScriptingError(_("install_or_extract only works with wine!"))
        if file_path.endswith(".exe"):
            params = {"name": "wineexec", "executable": file_id}
            return self.task(params)

        slug = self.installer.game_slug
        params = {"file": file_id, "dst": f"$GAMEDIR/drive_c/{slug}"}
        return self.extract(params)

    @staticmethod
    def _is_installer_exe(path):
        """Check if an .exe file is a known installer (NSIS or Inno Setup)."""
        try:
            with open(path, "rb") as f:
                header = f.read(512 * 1024)
            return b"NullsoftInst" in header or b"Inno Setup" in header
        except OSError:
            return False

    def extract_or_run(self, data):
        """Extract an archive. If extraction yields an installer exe (NSIS/Inno),
        run it with Wine instead of placing the files."""
        self._check_required_params("file", data, "extract_or_run")
        file_id = data["file"]
        dst = self._substitute(data.get("dst", "$CACHE"))
        file_path = self._get_file_path(file_id)

        # Extract the archive (e.g. tar.gz wrapper)
        self._killable_process(extract.extract_archive, file_path, dst, True)

        # Check if any extracted .exe is an installer
        for entry in os.listdir(dst):
            entry_path = os.path.join(dst, entry)
            if entry.lower().endswith(".exe") and os.path.isfile(entry_path) and self._is_installer_exe(entry_path):
                logger.info("Detected installer exe: %s, running with Wine", entry)
                params = {"name": "wineexec", "executable": entry_path}
                return self.task(params)

        # No installer found, merge the extracted files to the destination
        merge_dst = self._substitute(data.get("merge_dst", data.get("dst", "$GAMEDIR")))
        if merge_dst != dst:
            self.merge({"src": dst, "dst": merge_dst})

    def _check_path_within_target(self, path, command_name="command"):
        """Check that a resolved path is within the game's target directory.

        Logs a warning if target_path is not set (can't validate).  If the path
        is outside the game directory the user is prompted to allow or deny the
        operation.  Allowed parent directories are cached so the user is not
        asked repeatedly for the same location.
        """
        if not self.target_path:
            logger.warning("No target path set, cannot validate path for '%s': %s", command_name, path)
            return
        if system.path_contains(self.target_path, path):
            return

        resolved = os.path.realpath(path)

        # Check if this path falls under a directory the user already allowed.
        if not hasattr(self, "_allowed_external_paths"):
            self._allowed_external_paths = set()
        for allowed in self._allowed_external_paths:
            if system.path_contains(allowed, resolved):
                return

        # Ask the user via the UI delegate (blocks in the background thread
        # until the user responds).
        allowed = self.interpreter_ui_delegate.prompt_for_external_path(command_name, path, self.target_path)
        if allowed:
            # Cache the parent directory so sibling writes are auto-allowed.
            self._allowed_external_paths.add(os.path.dirname(resolved))
            logger.info("User allowed %s to write outside game directory: %s", command_name, path)
        else:
            raise ScriptingError(
                _("The {cmd} command was denied access to a path outside the game directory: {path}").format(
                    cmd=command_name, path=path
                )
            )
