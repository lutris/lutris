"""DOSBox installer commands"""
import os

from lutris.runners import import_runner
from lutris.util import system
from lutris.util.log import logger


def dosexec(config_file=None, executable=None, args=None, exit=True, working_dir=None):
    """Execute Dosbox with given config_file."""
    if config_file:
        run_with = "config {}".format(config_file)
        if not working_dir:
            working_dir = os.path.dirname(config_file)
    elif executable:
        run_with = "executable {}".format(executable)
        if not working_dir:
            working_dir = os.path.dirname(executable)
    else:
        raise ValueError("Neither a config file or an executable were provided")
    logger.debug("Running dosbox with %s", run_with)
    working_dir = system.create_folder(working_dir)
    dosbox = import_runner("dosbox")
    dosbox_runner = dosbox()
    command = [dosbox_runner.get_executable()]
    if config_file:
        command += ["-conf", config_file]
    if executable:
        if not system.path_exists(executable):
            raise OSError("Can't find file {}".format(executable))
        command += [executable]
    if args:
        command += args.split()
    if exit:
        command.append("-exit")
    system.execute(command, cwd=working_dir)


def makeconfig(path, drives, commands):
    system.create_folder(os.path.dirname(path))
    with open(path, "w") as config_file:
        config_file.write("[autoexec]\n")
        for drive in drives:
            config_file.write('mount {} "{}"\n'.format(drive, drives[drive]))
        for command in commands:
            config_file.write("{}\n".format(command))
