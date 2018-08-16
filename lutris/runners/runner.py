# -*- coding:Utf-8 -*-
"""Generic runner."""
import os
import platform
import shutil

from gi.repository import Gtk

from lutris import pga, settings, runtime
from lutris.config import LutrisConfig
from lutris.gui import dialogs
from lutris.thread import LutrisThread
from lutris.util.extract import extract_archive
from lutris.util.log import logger
from lutris.util import system
from lutris.util.http import Request
from lutris.runners import RunnerInstallationError


def get_arch():
    """Return the architecture returning values compatible with the reponses
    from the API
    """
    machine = platform.machine()
    if '64' in machine:
        return 'x86_64'
    elif '86' in machine:
        return 'i386'
    elif 'armv7' in machine:
        return 'armv7'


class Runner:
    """Generic runner (base class for other runners)."""
    multiple_versions = False
    platforms = []
    runnable_alone = False
    game_options = []
    runner_options = []
    system_options_override = []
    context_menu_entries = []
    depends_on = None
    runner_executable = None

    def __init__(self, config=None):
        """Initialize runner."""
        self.arch = get_arch()
        self.logger = logger
        self.config = config
        self.game_data = {}
        if config:
            self.game_data = pga.get_game_by_field(
                self.config.game_config_id, 'configpath'
            )

    def __lt__(self, other):
        return self.name < other.name

    @property
    def description(self):
        """Return the class' docstring as the description."""
        return self.__doc__

    @description.setter
    def description(self, value):
        """Leave the ability to override the docstring."""
        self.__doc__ = value

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def default_config(self):
        return LutrisConfig(runner_slug=self.name)

    @property
    def game_config(self):
        """Return the cascaded game config as a dict."""
        return self.config.game_config if self.config else {}

    @property
    def runner_config(self):
        """Return the cascaded runner config as a dict."""
        if self.config:
            return self.config.runner_config
        return self.default_config.runner_config

    @property
    def system_config(self):
        """Return the cascaded system config as a dict."""
        if self.config:
            return self.config.system_config
        return self.default_config.system_config

    @property
    def default_path(self):
        """Return the default path where games are installed."""
        return self.system_config.get('game_path')

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        for key in self.game_config:
            if key in ['exe', 'main_file', 'rom', 'disk', 'iso']:
                path = os.path.dirname(self.game_config.get(key) or '')
                if not os.path.isabs(path):
                    path = os.path.join(self.game_path, path)
                return path

        if self.game_data.get('directory'):
            return self.game_data.get('directory')

    @property
    def game_path(self):
        """Return the directory where the game is installed."""
        if self.game_data.get('directory'):
            return self.game_data.get('directory')
        return self.system_config.get('game_path')

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return os.path.expanduser("~/")

    def killall_on_exit(self):
        return True

    def get_platform(self):
        return self.platforms[0]

    def get_runner_options(self):
        runner_options = self.runner_options[:]
        if self.runner_executable:
            runner_options.append({
                'option': 'runner_executable',
                'type': 'file',
                'label': 'Custom executable for the runner',
                'advanced': True
            })
        return runner_options

    def get_executable(self):
        if 'runner_executable' in self.runner_config:
            runner_executable = self.runner_config['runner_executable']
            if os.path.isfile(runner_executable):
                return runner_executable
        if not self.runner_executable:
            raise ValueError('runner_executable not set for {}'.format(self.name))
        return os.path.join(settings.RUNNER_DIR, self.runner_executable)

    def get_env(self, os_env=False):
        """Return environment variables used for a game."""
        env = {}
        if os_env:
            env.update(os.environ.copy())

        system_env = self.system_config.get('env') or {}
        env.update(system_env)

        env["DRI_PRIME"] = "1" if self.system_config.get('dri_prime') else "0"

        runtime_ld_library_path = None

        if self.use_runtime():
            runtime_env = self.get_runtime_env()
            if 'STEAM_RUNTIME' in runtime_env and 'STEAM_RUNTIME' not in env:
                env['STEAM_RUNTIME'] = runtime_env['STEAM_RUNTIME']
            if 'LD_LIBRARY_PATH' in runtime_env:
                runtime_ld_library_path = runtime_env['LD_LIBRARY_PATH']

        if runtime_ld_library_path:
            ld_library_path = env.get("LD_LIBRARY_PATH")
            if not ld_library_path:
                ld_library_path = '$LD_LIBRARY_PATH'
            env["LD_LIBRARY_PATH"] = ":".join([runtime_ld_library_path, ld_library_path])

        return env

    def get_runtime_env(self):
        """Return runtime environment variables.

        This method may be overridden in runner classes.
        (Notably for Lutris wine builds)

        Returns:
            dict

        """
        return runtime.get_env(
            self.system_config.get('prefer_system_libs', True)
        )

    def play(self):
        """Dummy method, must be implemented by derived runnners."""
        raise NotImplementedError("Implement the play method in your runner")

    def get_run_data(self):
        """Return dict with command (exe & args list) and env vars (dict).

        Reimplement in derived runner if need be."""
        exe = self.get_executable()
        env = self.get_env()

        return {'command': [exe], 'env': env}

    def run(self, *args):
        """Run the runner alone."""
        if not self.runnable_alone:
            return
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return

        command_data = self.get_run_data()
        command = command_data.get('command')
        env = (command_data.get('env') or {}).copy()

        if hasattr(self, 'prelaunch'):
            self.prelaunch()

        thread = LutrisThread(command, runner=self, env=env, watch=False)
        thread.start()

    def use_runtime(self):
        if runtime.RUNTIME_DISABLED:
            logger.info("Runtime disabled by environment")
            return False
        if self.system_config.get('disable_runtime'):
            logger.info("Runtime disabled by system configuration")
            return False
        return True

    def install_dialog(self):
        """Ask the user if she wants to install the runner.

        Return success of runner installation.
        """
        dialog = dialogs.QuestionDialog({
            'question': ("The required runner is not installed.\n"
                         "Do you wish to install it now?"),
            'title': "Required runner unavailable"
        })
        if Gtk.ResponseType.YES == dialog.result:
            if hasattr(self, 'get_version'):
                version = self.get_version(use_default=False)
            else:
                version = None
            if version:
                return self.install(version=version)
            else:
                return self.install()
        return False

    def is_installed(self):
        """Return True if runner is installed else False."""
        executable = self.get_executable()
        if executable and os.path.exists(executable):
            return True

    def get_runner_info(self, version=None):
        runner_api_url = '{}/api/runners/{}'.format(settings.SITE_URL, self.name)
        logger.info("Getting runner information for %s%s", self.name, '(version: %s)' % version if version else '')
        request = Request(runner_api_url)
        response = request.get()
        response_content = response.json
        if response_content:
            versions = response_content.get('versions') or []
            logger.debug("Got %s versions", len(versions))
            arch = self.arch
            if version:
                if version.endswith('-i386') or version.endswith('-x86_64'):
                    version, arch = version.rsplit('-', 1)
                versions = [
                    v for v in versions if v['version'] == version
                ]
            versions_for_arch = [
                v for v in versions
                if v['architecture'] == arch
            ]
            if len(versions_for_arch) == 1:
                return versions_for_arch[0]
            elif len(versions_for_arch) > 1:
                default_version = [
                    v for v in versions_for_arch
                    if v['default'] is True
                ]
                if default_version:
                    return default_version[0]
            elif len(versions) == 1 and system.IS_64BIT:
                return versions[0]
            elif len(versions) > 1 and system.IS_64BIT:
                default_version = [
                    v for v in versions
                    if v['default'] is True
                ]
                if default_version:
                    return default_version[0]

    def install(self, version=None, downloader=None, callback=None):
        """Install runner using package management systems."""
        logger.debug("Installing %s (version=%s, downloader=%s, callback=%s)",
                     self.name, version, downloader, callback)
        runner_info = self.get_runner_info(version)
        if not runner_info:
            raise RunnerInstallationError(
                '{} is not available for the {} architecture'.format(
                    self.name, self.arch
                )
            )
            dialogs.ErrorDialog(
            )
            return False
        opts = {}
        if downloader:
            opts['downloader'] = downloader
        if callback:
            opts['callback'] = callback
        if 'wine' in self.name:
            version = runner_info['version']
            opts['merge_single'] = True
            dirname = '{}-{}'.format(version, runner_info['architecture'])
            opts['dest'] = os.path.join(settings.RUNNER_DIR,
                                        self.name, dirname)
        if self.name == 'libretro' and version:
            opts['merge_single'] = False
            opts['dest'] = os.path.join(settings.RUNNER_DIR, 'retroarch/cores')
        url = runner_info['url']
        self.download_and_extract(url, **opts)

    def download_and_extract(self, url, dest=None, **opts):
        merge_single = opts.get('merge_single', False)
        downloader = opts.get('downloader')
        callback = opts.get('callback')
        tarball_filename = os.path.basename(url)
        runner_archive = os.path.join(settings.CACHE_DIR, tarball_filename)
        if not dest:
            dest = settings.RUNNER_DIR
        if downloader:
            extract_args = {
                'archive': runner_archive,
                'dest': dest,
                'merge_single': merge_single,
                'callback': callback
            }
            downloader(url, runner_archive, self.on_downloaded, extract_args)
        else:
            dialog = dialogs.DownloadDialog(url, runner_archive)
            dialog.run()
            self.extract(archive=runner_archive, dest=dest, merge_single=merge_single,
                         callback=callback)

    def on_downloaded(self, widget, data, user_data):
        """GObject callback received by downloader"""
        self.extract(**user_data)

    def extract(self, archive=None, dest=None, merge_single=None,
                callback=None):
        if not os.path.exists(archive):
            raise RunnerInstallationError("Failed to extract {}", archive)
        extract_archive(archive, dest, merge_single=merge_single)
        os.remove(archive)
        if callback:
            callback()

    def remove_game_data(self, game_path=None):
        system.remove_folder(game_path)

    def uninstall(self):
        runner_path = os.path.join(settings.RUNNER_DIR, self.name)
        if os.path.isdir(runner_path):
            shutil.rmtree(runner_path)
