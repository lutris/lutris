"""Install games without GUI"""
# Standard Library
import os
import time
from gettext import gettext as _

# Lutris Modules
from lutris import settings
from lutris.installer import interpreter
from lutris.installer.errors import MissingGameDependency, ScriptingError
from lutris.util import jobs, system
from lutris.util.log import logger
from lutris.util.downloader import Downloader


class SilenInstall:

    """silent install process."""

    def __init__(
            self,
            game_slug=None,
            installer_file=None,
            revision=None,
            binary_path=None,
            install_path=None,
            cmd_print=None,  # get commandline output from application.py
            commandline=None
    ):

        self.interpreter = None
        self.game_slug = game_slug
        self.installer_file = installer_file
        self.revision = revision
        self.binary_path = binary_path
        self.install_path = install_path
        self.downloader = None
        self.bin_path_coutner = 0  # iterating throught the files
        self._print = cmd_print
        self.commandline = commandline

        if system.path_exists(self.installer_file):
            self.on_scripts_obtained(interpreter.read_script(self.installer_file))
        else:
            self._print(self.commandline, _("Waiting for response from %s" % settings.SITE_URL))
            logger.info(_("Waiting for response from %s" % settings.SITE_URL))
            jobs.AsyncCall(
                interpreter.fetch_script,
                self.on_scripts_obtained,
                self.game_slug,
                self.revision
            )

    def on_scripts_obtained(self, scripts, _error=None):
        if not scripts:
            self._print(self.commandline, "No install script found")
            logger.error("No install script found")
            return

        if isinstance(scripts, list):  # if scripts is a list longer than one element
            if len(scripts) != 1:
                self._print(self.commandline, "Please provide single installer")
                logger.error("No install script found")
                return
            self.script = scripts[0]
        else:
            self.script = scripts

        self.validate_scripts()
        self.prepare_install(self.script)

    def validate_scripts(self):
        """Auto-fixes some script aspects and checks for mandatory fields"""

        for item in ["description", "notes"]:
            self.script[item] = self.script.get(item) or ""
        for item in ["name", "runner", "version"]:
            if item not in self.script:
                self._print(self.commandline, _("Invalid script: %s" % self.script))
                raise ScriptingError('Missing field "%s" in install script' % item)

    def prepare_install(self, script):

        install_script = script
        if not install_script:
            raise ValueError("Could not find script %s" % install_script)
        try:
            self.interpreter = interpreter.ScriptInterpreter(install_script, self)
        except MissingGameDependency as ex:
            # call recursive dependencies
            SilenInstall(
                game_slug=ex.slug
            )

        self.select_install_folder()

    def select_install_folder(self):
        """Stage where we select the install directory."""
        if self.interpreter.creates_game_folder:
            if self.install_path is None:
                self.install_path = self.interpreter.get_default_target()

            self.interpreter.target_path = self.install_path
            self._print(self.commandline, _("install Folder %s" % self.interpreter.target_path))
            logger.info("No install script found")

        try:
            self.interpreter.check_runner_install()
        except ScriptingError as ex:
            self._print(self.commandline, ex.__str__)
            logger.error(ex.__str__)
            return

    def set_status(self, text):
        self._print(self.commandline, text)

    # required by interpreter
    def clean_widgets(self):
        pass

    # required by interpreter
    def add_spinner(self):
        pass

    # required by interpreter
    def set_cancle_butten_sensitive(self):
        pass

    # required by interpreter
    def continue_button_hide(self):
        pass

    def attach_logger(self, command):
        pass

    def on_install_error(self, message):
        self._print(self.commandline, message)
        logger.error(message)
        exit()
        # end program

    def on_install_finished(self):
        self._print(self.commandline, "finished install")
        logger.info("finished install")
        exit()
        # end program

    def input_menu(self, alias, options, preselect, has_entry, callback):
        """Display an input request as a dropdown menu with options."""
        # not sure what to do here...
        self._print(self.commandline, "input menu not supported for silent install")
        logger.error("input menu not supported for silent install")
        return

    def ask_user_for_file(self, message):
        if not os.path.isfile(self.binary_path[self.bin_path_coutner]):
            self._print(self.commandline, _("%s is not a file" % self.binary_path[self.bin_path_coutner]))
            logger.warning("%s is not a file", self.binary_path[self.bin_path_coutner])
            return
        logger.info("use %s", self.binary_path[self.bin_path_coutner])
        self.interpreter.file_selected(self.binary_path[self.bin_path_coutner])
        self.bin_path_coutner += 1

    def start_download(self, file_uri, dest_file, callback=None, data=None, referer=None):
        try:
            self.downloader = Downloader(file_uri, dest_file, referer=referer, overwrite=True)
        except RuntimeError as ex:
            self._print(self.commandline, _("Downloading  %s to %s has an error: %s") %
                        (file_uri, dest_file, ex.__str__))
            logger.error("Downloading  %s to %s has an error: %s", file_uri, dest_file, ex.__str__)
            return None

        self._print(self.commandline, _("Downloading %s to %s") % (file_uri, dest_file))
        logger.info("Downloading %s to %s", file_uri, dest_file)
        self.downloader.start()

        while self.downloader.check_progress() != 1.0:
            self.download_progress()
            time.sleep(0.5)

        self.on_download_complete(callback, data)

    def download_progress(self):
        """Show download progress."""
        if self.downloader.state in [self.downloader.CANCELLED, self.downloader.ERROR]:
            if self.downloader.state == self.downloader.CANCELLED:
                self._print(self.commandline, "Download interrupted")
                logger.error("Download interrupted")
            else:
                self._print(self.commandline, self.downloader.error)
            if self.downloader.state == self.downloader.CANCELLED:
                self._print(self.commandline, "Download canceled")
                logger.error("Download canceled")
            return
        megabytes = 1024 * 1024
        self._print(self.commandline, _((
            "{downloaded:0.2f} / {size:0.2f}MB ({speed:0.2f}MB/s), {time} remaining"
        ).format(
            downloaded=float(self.downloader.downloaded_size) / megabytes,
            size=float(self.downloader.full_size) / megabytes,
            speed=float(self.downloader.average_speed) / megabytes,
            time=self.downloader.time_left,
        )))

    def on_download_complete(self, callback=None, callback_data=None):
        """Action called on a completed download."""
        if callback:
            try:
                callback_data = callback_data or {}
                callback(**callback_data)
            except Exception as ex:  # pylint: disable:broad-except
                raise ScriptingError(str(ex))

        self.interpreter.abort_current_task = None
        self.interpreter.iter_game_files()

    def ask_for_disc(self, message, callback, requires):
        """Ask the user to do insert a CD-ROM."""
        callback(requires)
