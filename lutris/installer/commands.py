import multiprocessing
import os
import shutil
import shlex

from gi.repository import Gdk

from .errors import ScriptingError

from lutris import runtime
from lutris.util import extract, devices, system
from lutris.util.fileio import EvilConfigParser, MultiOrderedDict
from lutris.util.log import logger

from lutris.runners import wine, import_task, import_runner, InvalidRunner
from lutris.thread import LutrisThread


class Commands(object):
    """The directives for the `installer:` part of the install script."""

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
        os.popen('chmod +x "%s"' % filename)

    def execute(self, data):
        """Run an executable file."""
        args = []
        if isinstance(data, dict):
            self._check_required_params('file', data, 'execute')
            file_ref = data['file']
            args_string = data.get('args', '')
            for arg in shlex.split(args_string):
                args.append(self._substitute(arg))
        else:
            file_ref = data
        # Determine whether 'file' value is a file id or a path
        exec_path = self._get_file(file_ref) or self._substitute(file_ref)
        if not exec_path:
            raise ScriptingError("Unable to find file %s" % file_ref,
                                 file_ref)
        if not os.path.exists(exec_path):
            raise ScriptingError("Unable to find required executable",
                                 exec_path)
        self.chmodx(exec_path)

        terminal = data.get('terminal')
        if terminal:
            terminal = system.get_default_terminal()

        command = [exec_path] + args
        logger.debug("Executing %s" % command)
        thread = LutrisThread(command, env=runtime.get_env(), term=terminal,
                              cwd=self.target_path, watch=False)
        self.abort_current_task = thread.killall
        thread.run()
        self.abort_current_task = None

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
        self.parent.set_status(msg)
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
        self.parent.input_menu(alias, options, preselect, has_entry,
                               self._on_input_menu_validated)
        return 'STOP'

    def _on_input_menu_validated(self, widget, *args):
        alias = args[0]
        menu = args[1]
        choosen_option = menu.get_active_id()
        if choosen_option:
            self.user_inputs.append({'alias': alias,
                                     'value': choosen_option})
            self.parent.continue_button.hide()
            self._iter_commands()

    def insert_disc(self, data):
        self._check_required_params('requires', data, 'insert_disc')
        requires = data.get('requires')
        message = data.get(
            'message',
            "Insert game disc or mount disk image and click OK."
        )
        message += (
            "\n\nLutris is looking for a mounted disk drive or image \n"
            "containing the following file or folder:\n"
            "<i>%s</i>" % requires
        )
        self.parent.wait_for_user_action(message, self._find_matching_disc,
                                         requires)
        return 'STOP'

    def _find_matching_disc(self, widget, requires):
        drives = devices.get_mounted_discs()
        for drive in drives:
            mount_point = drive.get_root().get_path()
            required_abspath = os.path.join(mount_point, requires)
            required_abspath = system.fix_path_case(required_abspath)
            if required_abspath:
                logger.debug("Found %s on cdrom %s" % (requires, mount_point))
                self.game_disc = mount_point
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
        dst = dst.rstrip('/')
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        os.rename(src, dst)

    def _get_move_paths(self, params):
        """Process raw 'src' and 'dst' data."""
        src_ref = params['src']
        src = (self.game_files.get(src_ref) or self._substitute(src_ref))
        if not src:
            raise ScriptingError("Wrong value for 'src' param", src_ref)
        dst_ref = params['dst']
        dst = self._substitute(dst_ref)
        if not dst:
            raise ScriptingError("Wrong value for 'dst' param", dst_ref)
        return (src, dst)

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

    def task(self, data):
        """Directive triggering another function specific to a runner.

        The 'name' parameter is mandatory. If 'args' is provided it will be
        passed to the runner task.
        """
        self._check_required_params('name', data, 'task')
        self.parent.cancel_button.set_sensitive(False)
        task_name = data.pop('name')
        if '.' in task_name:
            # Run a task from a different runner
            # than the one for this installer
            runner_name, task_name = task_name.split('.')
        else:
            runner_name = self.script["runner"]
        try:
            runner_class = import_runner(runner_name)
        except InvalidRunner:
            self.parent.cancel_button.set_sensitive(True)
            raise ScriptingError('Invalid runner provided %s', runner_name)

        runner = runner_class()

        # Check/install Wine runner at version specified in the script
        wine_version = None
        if runner_name == 'wine' and self.script.get('wine'):
            wine_version = self.script.get('wine').get('version')

            # Old lutris versions used a version + arch tuple, we now include
            # everything in the version.
            # Before that change every wine runner was for i386
            if '-' not in wine_version:
                wine_version += '-i386'

        if wine_version and task_name == 'wineexec':
            if not wine.is_version_installed(wine_version):
                Gdk.threads_init()
                Gdk.threads_enter()
                runner.install(wine_version)
                Gdk.threads_leave()
            data['wine_path'] = wine.get_wine_version_exe(wine_version)
        # Check/install other runner
        elif not runner.is_installed():
            Gdk.threads_init()
            Gdk.threads_enter()
            runner.install()
            Gdk.threads_leave()

        for key in data:
            data[key] = self._substitute(data[key])
        task = import_task(runner_name, task_name)
        task(**data)
        self.parent.cancel_button.set_sensitive(True)

    def write_config(self, params):
        self._check_required_params(['file', 'section', 'key', 'value'],
                                    params, 'move')
        """Write a key-value pair into an INI type config file."""
        # Get file
        config_file = self._get_file(params['file'])
        if not config_file:
            config_file = self._substitute(params['file'])

        # Create it if necessary
        basedir = os.path.dirname(config_file)
        if not os.path.exists(basedir):
            os.makedirs(basedir)

        parser = EvilConfigParser(allow_no_value=True,
                                  dict_type=MultiOrderedDict)
        parser.optionxform = str  # Preserve text case
        parser.read(config_file)

        if not parser.has_section(params['section']):
            parser.add_section(params['section'])
        parser.set(params['section'], params['key'], params['value'])

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
