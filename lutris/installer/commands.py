import multiprocessing
import os
import stat
import shutil
import shlex
import json

from gi.repository import GLib

from lutris.installer.errors import ScriptingError

from lutris import runtime
from lutris.util import extract, disks, system
from lutris.util.fileio import EvilConfigParser, MultiOrderedDict
from lutris.util.log import logger

from lutris.runners import wine, import_task
from lutris.thread import LutrisThread


def selective_merge(base_obj, delta_obj):
    """ used by write_json """
    if not isinstance(base_obj, dict):
        return delta_obj
    common_keys = set(base_obj).intersection(delta_obj)
    new_keys = set(delta_obj).difference(common_keys)
    for k in common_keys:
        base_obj[k] = selective_merge(base_obj[k], delta_obj[k])
    for k in new_keys:
        base_obj[k] = delta_obj[k]
    return base_obj


class CommandsMixin(object):
    """The directives for the `installer:` part of the install script."""

    def __init__(self):
        raise RuntimeError("Don't instanciate this class, it's a mixin!!!!!!!!!!!!!!!!")

    def _get_runner_version(self):
        if self.script.get('wine'):
            return wine.support_legacy_version(self.script['wine'].get('version'))
        if self.runner == 'libretro':
            return self.script['game']['core']

    def _check_required_params(self, params, command_data, command_name):
        """Verify presence of a list of parameters required by a command."""
        if type(params) is str:
            params = [params]
        for param in params:
            if param not in command_data:
                raise ScriptingError('The "%s" parameter is mandatory for '
                                     'the %s command' % (param, command_name),
                                     command_data)

    def check_md5(self, data):
        self._check_required_params(['file', 'value'], data, 'check_md5')
        filename = self._substitute(data['file'])
        hash_string = self._killable_process(system.get_md5_hash, filename)

        if hash_string != data['value']:
            raise ScriptingError("MD5 checksum mismatch", data)
        self._iter_commands()

    def chmodx(self, filename):
        filename = self._substitute(filename)
        st = os.stat(filename)
        os.chmod(filename, st.st_mode | stat.S_IEXEC)

    def execute(self, data):
        """Run an executable file."""
        args = []
        terminal = None
        working_dir = None
        env = {}
        if isinstance(data, dict):
            if 'command' not in data and 'file' not in data:
                raise ScriptingError('Parameter file or command is mandatory '
                                     'for the execute command', data)
            elif 'command' in data and 'file' in data:
                raise ScriptingError('Parameters file and command can\'t be '
                                     'used at the same time for the execute '
                                     'command', data)
            file_ref = data.get('file', '')
            command = data.get('command', '')
            args_string = data.get('args', '')
            for arg in shlex.split(args_string):
                args.append(self._substitute(arg))
            terminal = data.get('terminal')
            working_dir = data.get('working_dir')
            if not data.get('disable_runtime', False):
                env.update(runtime.get_env())
            userenv = data.get('env', {})
            for key in userenv:
                v = userenv[key]
                userenv[key] = self._get_file(v) or self._substitute(v)
            env.update(userenv)
            include_processes = data.get('include_processes', '').split(' ')
            exclude_processes = data.get('exclude_processes', '').split(' ')
        elif isinstance(data, str):
            command = data
            include_processes = []
            exclude_processes = []
        else:
            raise ScriptingError('No parameters supplied to execute command.', data)

        if command:
            command = command.strip()
            command = self._get_file(command) or self._substitute(command)
            file_ref = 'bash'
            args = ['-c', command]
            include_processes.append('bash')
        else:
            # Determine whether 'file' value is a file id or a path
            file_ref = self._get_file(file_ref) or self._substitute(file_ref)

        exec_path = system.find_executable(file_ref)
        if not exec_path:
            raise ScriptingError("Unable to find executable %s" % file_ref)
        if not os.access(exec_path, os.X_OK):
            self.chmodx(exec_path)

        if terminal:
            terminal = system.get_default_terminal()

        if not working_dir or not os.path.exists(working_dir):
            working_dir = self.target_path

        command = [exec_path] + args
        logger.debug("Executing %s" % command)
        thread = LutrisThread(command, env=env, term=terminal, cwd=working_dir,
                              include_processes=include_processes,
                              exclude_processes=exclude_processes)
        thread.start()
        GLib.idle_add(self.parent.attach_logger, thread)
        self.heartbeat = GLib.timeout_add(1000, self._monitor_task, thread)
        return 'STOP'

    def extract(self, data):
        """Extract a file, guessing the compression method."""
        self._check_required_params('file', data, 'extract')
        filename = self._get_file(data['file'])
        if not filename:
            filename = self._substitute(data['file'])

        if not os.path.exists(filename):
            raise ScriptingError("%s does not exists" % filename)
        if 'dst' in data:
            dest_path = self._substitute(data['dst'])
        else:
            dest_path = self.target_path
        msg = "Extracting %s" % os.path.basename(filename)
        logger.debug(msg)
        GLib.idle_add(self.parent.set_status, msg)
        merge_single = 'nomerge' not in data
        extractor = data.get('format')
        logger.debug("extracting file %s to %s", filename, dest_path)

        self._killable_process(extract.extract_archive, filename, dest_path,
                               merge_single, extractor)

    def input_menu(self, data):
        """Display an input request as a dropdown menu with options."""
        self._check_required_params('options', data, 'input_menu')
        identifier = data.get('id')
        alias = 'INPUT_%s' % identifier if identifier else None
        has_entry = data.get('entry')
        options = data['options']
        preselect = self._substitute(data.get('preselect', ''))
        GLib.idle_add(self.parent.input_menu, alias, options, preselect,
                      has_entry, self._on_input_menu_validated)
        return 'STOP'

    def _on_input_menu_validated(self, widget, *args):
        alias = args[0]
        menu = args[1]
        choosen_option = menu.get_active_id()
        if choosen_option:
            self.user_inputs.append({'alias': alias,
                                     'value': choosen_option})
            GLib.idle_add(self.parent.continue_button.hide)
            self._iter_commands()

    def insert_disc(self, data):
        self._check_required_params('requires', data, 'insert_disc')
        requires = data.get('requires')
        message = data.get(
            'message',
            "Insert or mount game disc and click Autodetect or\n"
            "use Browse if the disc is mounted on a non standard location."
        )
        message += (
            "\n\nLutris is looking for a mounted disk drive or image \n"
            "containing the following file or folder:\n"
            "<i>%s</i>" % requires
        )
        if self.runner == 'wine':
            GLib.idle_add(self.parent.eject_button.show)
        GLib.idle_add(self.parent.ask_for_disc, message,
                      self._find_matching_disc, requires)
        return 'STOP'

    def _find_matching_disc(self, widget, requires, extra_path=None):
        if extra_path:
            drives = [extra_path]
        else:
            drives = disks.get_mounted_discs()
        for drive in drives:
            required_abspath = os.path.join(drive, requires)
            required_abspath = system.fix_path_case(required_abspath)
            if required_abspath:
                logger.debug("Found %s on cdrom %s" % (requires, drive))
                self.game_disc = drive
                self._iter_commands()
                break

    def mkdir(self, directory):
        directory = self._substitute(directory)
        try:
            os.makedirs(directory)
        except OSError:
            logger.debug("Directory %s already exists" % directory)
        else:
            logger.debug("Created directory %s" % directory)

    def merge(self, params):
        self._check_required_params(['src', 'dst'], params, 'merge')
        src, dst = self._get_move_paths(params)
        logger.debug("Merging %s into %s" % (src, dst))
        if not os.path.exists(src):
            raise ScriptingError("Source does not exist: %s" % src, params)
        if not os.path.exists(dst):
            os.makedirs(dst)
        if os.path.isfile(src):
            # If single file, copy it and change reference in game file so it
            # can be used as executable. Skip copying if the source is the same
            # as destination.
            if os.path.dirname(src) != dst:
                self._killable_process(shutil.copy, src, dst)
            if params['src'] in self.game_files.keys():
                self.game_files[params['src']] = os.path.join(
                    dst, os.path.basename(src)
                )
            return
        self._killable_process(system.merge_folders, src, dst)

    def move(self, params):
        """Move a file or directory into a destination folder."""
        self._check_required_params(['src', 'dst'], params, 'move')
        src, dst = self._get_move_paths(params)
        logger.debug("Moving %s to %s" % (src, dst))
        if not os.path.exists(src):
            raise ScriptingError("I can't move %s, it does not exist" % src)
        if os.path.isfile(src):
            src_filename = os.path.basename(src)
            src_dir = os.path.dirname(src)
            dst_path = os.path.join(dst, src_filename)
            if src_dir == dst:
                logger.info("Source file is the same as destination, skipping")
            elif os.path.exists(dst_path):
                # May not be the best choice, but it's the safest.
                # Maybe should display confirmation dialog (Overwrite / Skip) ?
                logger.info("Destination file exists, skipping")
            else:
                self._killable_process(shutil.move, src, dst)
        else:
            try:
                self._killable_process(shutil.move, src, dst)
            except shutil.Error:
                raise ScriptingError("Can't move %s \nto destination %s"
                                     % (src, dst))
        if os.path.isfile(src) and params['src'] in self.game_files.keys():
            # Change game file reference so it can be used as executable
            self.game_files['src'] = src

    def rename(self, params):
        """Rename file or folder."""
        self._check_required_params(['src', 'dst'], params, 'rename')
        src, dst = self._get_move_paths(params)
        if not os.path.exists(src):
            raise ScriptingError("Rename error, source path does not exist: %s"
                                 % src)
        if os.path.isdir(dst):
            os.rmdir(dst)  # Remove if empty
        if os.path.exists(dst):
            raise ScriptingError("Rename error, destination already exists: %s"
                                 % src)
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
            src_ref = params['src']
        except KeyError:
            raise ScriptingError('Missing parameter src')
        src = (self.game_files.get(src_ref) or self._substitute(src_ref))
        if not src:
            raise ScriptingError("Wrong value for 'src' param", src_ref)
        dst_ref = params['dst']
        dst = self._substitute(dst_ref)
        if not dst:
            raise ScriptingError("Wrong value for 'dst' param", dst_ref)
        return (src.rstrip('/'), dst.rstrip('/'))

    def substitute_vars(self, data):
        """Subsitute variable names found in given file."""
        self._check_required_params('file', data, 'substitute_vars')
        filename = self._substitute(data['file'])
        logger.debug('Substituting variables for file %s', filename)
        tmp_filename = filename + '.tmp'
        with open(filename, 'r') as source_file:
            with open(tmp_filename, 'w') as dest_file:
                line = '.'
                while line:
                    line = source_file.readline()
                    line = self._substitute(line)
                    dest_file.write(line)
        os.rename(tmp_filename, filename)

    def _get_task_runner_and_name(self, task_name):
        if '.' in task_name:
            # Run a task from a different runner
            # than the one for this installer
            runner_name, task_name = task_name.split('.')
        else:
            runner_name = self.runner
        return runner_name, task_name

    def task(self, data):
        """Directive triggering another function specific to a runner.

        The 'name' parameter is mandatory. If 'args' is provided it will be
        passed to the runner task.
        """
        self._check_required_params('name', data, 'task')
        if self.parent:
            GLib.idle_add(self.parent.cancel_button.set_sensitive, False)
        runner_name, task_name = self._get_task_runner_and_name(data.pop('name'))

        wine_version = None
        if runner_name == 'wine':
            wine_version = self._get_runner_version()

        if runner_name.startswith('wine'):
            if wine_version:
                data['wine_path'] = wine.get_wine_version_exe(wine_version)

        for key in data:
            value = data[key]
            if type(value) is dict:
                for inner_key in value:
                    value[inner_key] = self._substitute(value[inner_key])
            elif type(value) is list:
                for index, elem in enumerate(value):
                    value[index] = self._substitute(elem)
            else:
                value = self._substitute(data[key])
            data[key] = value

        if runner_name in ['wine', 'winesteam'] and 'prefix' not in data:
            data['prefix'] = self.target_path

        task = import_task(runner_name, task_name)
        thread = task(**data)
        GLib.idle_add(self.parent.cancel_button.set_sensitive, True)
        if isinstance(thread, LutrisThread):
            # Monitor thread and continue when task has executed
            GLib.idle_add(self.parent.attach_logger, thread)
            self.heartbeat = GLib.timeout_add(1000, self._monitor_task, thread)
            return 'STOP'

    def _monitor_task(self, thread):
        if not thread.is_running:
            self._iter_commands()
            return False
        return True

    def write_file(self, params):
        """Write text to a file."""
        self._check_required_params(['file', 'content'], params, 'write_file')

        # Get file
        file = self._get_file(params['file']) or self._substitute(params['file'])

        # Create dir if necessary
        basedir = os.path.dirname(file)
        if not os.path.exists(basedir):
            os.makedirs(basedir)

        mode = params.get('mode', 'w')

        with open(file, mode) as f:
            f.write(params['file'])

    def write_json(self, params):
        """Write data into a json file."""
        self._check_required_params(['file', 'data'], params, 'write_json')

        # Get file
        file = self._get_file(params['file']) or self._substitute(params['file'])

        # Create dir if necessary
        basedir = os.path.dirname(file)
        if not os.path.exists(basedir):
            os.makedirs(basedir)

        merge = params.get('merge', True)

        with open(file, 'a+') as f:
            pass

        with open(file, 'r+' if merge else 'w') as f:
            data = {}
            if merge:
                try:
                    data = json.load(f)
                except ValueError:
                    pass

            data = selective_merge(data, params.get('data', {}))
            f.seek(0)
            f.write(json.dumps(data, indent=2))

    def write_config(self, params):
        """Write a key-value pair into an INI type config file."""
        self._check_required_params(['file', 'section', 'key', 'value'],
                                    params, 'write_config')
        # Get file
        config_file = (self._get_file(params['file']) or
                       self._substitute(params['file']))

        # Create dir if necessary
        basedir = os.path.dirname(config_file)
        if not os.path.exists(basedir):
            os.makedirs(basedir)

        parser = EvilConfigParser(allow_no_value=True,
                                  dict_type=MultiOrderedDict,
                                  strict=False)
        parser.optionxform = str  # Preserve text case
        parser.read(config_file)

        value = self._substitute(params['value'])

        if not parser.has_section(params['section']):
            parser.add_section(params['section'])
        parser.set(params['section'], params['key'], value)

        with open(config_file, 'wb') as f:
            parser.write(f)

    def _get_file(self, fileid):
        return self.game_files.get(fileid)

    def _killable_process(self, func, *args, **kwargs):
        """Run function `func` in a separate, killable process."""
        process = multiprocessing.Pool(1)
        result_obj = process.apply_async(func, args, kwargs)
        self.abort_current_task = process.terminate
        result = result_obj.get()  # Wait process end & reraise exceptions
        self.abort_current_task = None
        return result
