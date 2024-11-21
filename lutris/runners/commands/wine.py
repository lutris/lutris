"""Wine commands for installers"""

# pylint: disable=too-many-arguments
import os
import shlex
import time

from lutris import runtime, settings
from lutris.monitored_command import MonitoredCommand
from lutris.runners import import_runner
from lutris.util import linux, system
from lutris.util.log import logger
from lutris.util.shell import get_shell_command
from lutris.util.strings import split_arguments
from lutris.util.wine import proton
from lutris.util.wine.cabinstall import CabInstaller
from lutris.util.wine.prefix import WinePrefixManager
from lutris.util.wine.wine import (
    WINE_DEFAULT_ARCH,
    WINE_DIR,
    detect_arch,
    get_overrides_env,
    get_real_executable,
    is_installed_systemwide,
    is_prefix_directory,
)


def set_regedit(
    path,
    key,
    value="",
    type="REG_SZ",  # pylint: disable=redefined-builtin
    wine_path=None,
    prefix=None,
    arch=WINE_DEFAULT_ARCH,
):
    """Add keys to the windows registry.

    Path is something like HKEY_CURRENT_USER/Software/Wine/Direct3D
    """
    formatted_value = {
        "REG_SZ": '"%s"' % value,
        "REG_DWORD": "dword:" + value,
        "REG_BINARY": "hex:" + value.replace(" ", ","),
        "REG_MULTI_SZ": "hex(2):" + value,
        "REG_EXPAND_SZ": "hex(7):" + value,
    }
    # Make temporary reg file
    reg_path = os.path.join(settings.CACHE_DIR, "winekeys.reg")
    with open(reg_path, "w", encoding="utf-8") as reg_file:
        reg_file.write('REGEDIT4\n\n[%s]\n"%s"=%s\n' % (path, key, formatted_value[type]))
    logger.debug("Setting [%s]:%s=%s", path, key, formatted_value[type])
    set_regedit_file(reg_path, wine_path=wine_path, prefix=prefix, arch=arch)
    os.remove(reg_path)


def set_regedit_file(filename, wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH, proton_verb=None):
    """Apply a regedit file to the Windows registry."""
    if arch == "win64" and wine_path and system.path_exists(wine_path + "64"):
        # Use wine64 by default if set to a 64bit prefix. Using regular wine
        # will prevent some registry keys from being created. Most likely to be
        # a bug in Wine. see: https://github.com/lutris/lutris/issues/804
        wine_path = wine_path + "64"

    if proton.is_proton_path(wine_path):
        proton_verb = "run"

    wineexec(
        "regedit",
        args="/S '%s'" % filename,
        wine_path=wine_path,
        prefix=prefix,
        arch=arch,
        blocking=True,
        proton_verb=proton_verb,
    )


def delete_registry_key(key, wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH, proton_verb=None):
    """Deletes a registry key from a Wine prefix"""

    if proton.is_proton_path(wine_path):
        proton_verb = "run"

    wineexec(
        "regedit",
        args='/S /D "%s"' % key,
        wine_path=wine_path,
        prefix=prefix,
        arch=arch,
        blocking=True,
        proton_verb=proton_verb,
    )


def create_prefix(
    prefix,
    wine_path=None,
    arch=WINE_DEFAULT_ARCH,
    overrides=None,
    install_gecko=None,
    install_mono=None,
    runner=None,
    env=None,
    proton_verb=None,
):
    """Create a new Wine prefix."""
    # pylint: disable=too-many-locals
    if overrides is None:
        overrides = {}
    if not prefix:
        raise ValueError("No Wine prefix path given")
    prefix = os.path.expanduser(prefix)
    logger.info("Creating a %s prefix in %s", arch, prefix)

    # Follow symlinks, don't delete existing ones as it would break some setups
    if os.path.islink(prefix):
        prefix = os.readlink(prefix)

    # Avoid issue of 64bit Wine refusing to create win32 prefix
    # over an existing empty folder.
    if os.path.isdir(prefix) and not os.listdir(prefix):
        try:
            os.rmdir(prefix)
        except OSError:
            logger.error("Failed to delete %s, you may lack permissions on this folder.", prefix)

    if not wine_path:
        if not runner:
            runner = import_runner("wine")()
        wine_path = runner.get_executable()

    logger.info("Winepath: %s", wine_path)

    wineenv = {
        "WINEARCH": arch,
        "WINEPREFIX": prefix,
        "WINEDLLOVERRIDES": get_overrides_env(overrides),
        "WINE_MONO_CACHE_DIR": os.path.join(os.path.dirname(os.path.dirname(wine_path)), "mono"),
        "WINE_GECKO_CACHE_DIR": os.path.join(os.path.dirname(os.path.dirname(wine_path)), "gecko"),
    }

    if install_gecko == "False":
        wineenv["WINE_SKIP_GECKO_INSTALLATION"] = "1"
        overrides["mshtml"] = "disabled"
    if install_mono == "False":
        wineenv["WINE_SKIP_MONO_INSTALLATION"] = "1"
        overrides["mscoree"] = "disabled"

    if proton.is_proton_path(wine_path):
        # All proton path prefixes are created via Umu; if you aren't using
        # the default Umu, we'll use PROTONPATH to indicate what Proton is
        # to be used.
        wineenv["PROTON_VERB"] = "run"

        proton.update_proton_env(wine_path, wineenv)

        command = MonitoredCommand([proton.get_umu_path(), "createprefix"], env=wineenv)
        command.start()
    else:
        wineboot_path = os.path.join(os.path.dirname(wine_path), "wineboot")
        if not system.path_exists(wineboot_path):
            logger.error(
                "No wineboot executable found in %s, " "your wine installation is most likely broken",
                wine_path,
            )
            return

        system.execute([wineboot_path], env=wineenv)

    for loop_index in range(1000):
        time.sleep(0.5)
        if (
            system.path_exists(os.path.join(prefix, "user.reg"))
            and system.path_exists(os.path.join(prefix, "userdef.reg"))
            and system.path_exists(os.path.join(prefix, "system.reg"))
        ):
            break
        if loop_index == 60:
            logger.warning("Wine prefix creation is taking longer than expected...")
    if not os.path.exists(os.path.join(prefix, "user.reg")):
        logger.error("No user.reg found after prefix creation. Prefix might not be valid")
        return
    logger.info("%s Prefix created in %s", arch, prefix)
    prefix_manager = WinePrefixManager(prefix)
    prefix_manager.setup_defaults()


def winekill(prefix, arch=WINE_DEFAULT_ARCH, wine_path=None, env=None, initial_pids=None, runner=None):
    """Kill processes in Wine prefix."""

    initial_pids = initial_pids or []
    if not env:
        env = {"WINEARCH": arch, "WINEPREFIX": prefix}
    if proton.is_proton_path(wine_path):
        command = [proton.get_umu_path(), "wineboot", "-k"]
        env["GAMEID"] = proton.DEFAULT_GAMEID
        env["WINEPREFIX"] = prefix
        env["PROTON_VERB"] = "runinprefix"
        env["PROTONPATH"] = proton.get_proton_path_by_path(wine_path)
    else:
        if not wine_path:
            if not runner:
                runner = import_runner("wine")()
            wine_path = runner.get_executable()
        wine_root = os.path.dirname(wine_path)

        command = [os.path.join(wine_root, "wineserver"), "-k"]
        logger.debug("Killing all wine processes (%s) in prefix %s: %s", initial_pids, prefix, command)
    logger.debug(command)
    logger.debug(" ".join(command))
    system.execute(command, env=env, quiet=True)

    logger.debug("Waiting for wine processes to terminate")
    # Wineserver needs time to terminate processes
    num_cycles = 0
    while True:
        num_cycles += 1
        running_processes = [pid for pid in initial_pids if system.path_exists("/proc/%s" % pid)]

        if not running_processes:
            break
        if num_cycles > 20:
            logger.warning(
                "Some wine processes are still running: %s",
                ", ".join(running_processes),
            )
            break
        time.sleep(0.1)
    logger.debug("Done waiting.")


def use_lutris_runtime(wine_path, force_disable=False):
    """Returns whether to use the Lutris runtime.
    The runtime can be forced to be disabled, otherwise
    it's disabled automatically if Wine is installed system wide.
    """
    if proton.is_proton_path(wine_path):
        return False
    if force_disable or runtime.RUNTIME_DISABLED:
        return False
    if WINE_DIR in wine_path:
        return True
    if is_installed_systemwide():
        return False
    return True


# pragma pylint: disable=too-many-locals
def wineexec(
    executable,
    args="",
    wine_path=None,
    prefix=None,
    arch=None,
    working_dir=None,
    winetricks_wine="",
    blocking=False,
    config=None,
    include_processes=None,
    exclude_processes=None,
    disable_runtime=False,
    env=None,
    overrides=None,
    runner=None,
    proton_verb=None,
):
    """
    Execute a Wine command.

    Args:
        executable (str): wine program to run, pass None to run wine itself
        args (str): program arguments
        wine_path (str): path to the wine version to use
        prefix (str): path to the wine prefix to use
        arch (str): wine architecture of the prefix
        working_dir (str): path to the working dir for the process
        winetricks_wine (str): path to the wine version used by winetricks
        blocking (bool): if true, do not run the process in a thread
        config (LutrisConfig): LutrisConfig object for the process context
        watch (list): list of process names to monitor (even when in a ignore list)
        runner (runner): the wine runner that carries the configuration to use

    Returns:
        Process results if the process is running in blocking mode or
        MonitoredCommand instance otherwise.
    """
    if env is None:
        env = {}
    if exclude_processes is None:
        exclude_processes = []
    if include_processes is None:
        include_processes = []
    executable = str(executable) if executable else ""
    if isinstance(include_processes, str):
        include_processes = shlex.split(include_processes)
    if isinstance(exclude_processes, str):
        exclude_processes = shlex.split(exclude_processes)

    if not runner:
        runner = import_runner("wine")(prefix=prefix, working_dir=working_dir, wine_arch=arch)

    if not wine_path:
        wine_path = runner.get_executable()

    if not working_dir:
        if os.path.isfile(executable):
            working_dir = os.path.dirname(executable)

    executable, _args, working_dir = get_real_executable(executable, working_dir)
    if _args:
        args = '{} "{}"'.format(_args[0], _args[1])

    wineenv = {"WINEARCH": arch}
    if winetricks_wine and winetricks_wine is not wine_path and not proton.is_proton_path(wine_path):
        wineenv["WINE"] = winetricks_wine
    else:
        wineenv["WINE"] = wine_path

    if prefix:
        wineenv["WINEPREFIX"] = prefix

    # Create prefix if necessary
    if arch not in ("win32", "win64"):
        arch = detect_arch(prefix, wine_path)
    if not is_prefix_directory(prefix):
        wine_bin = winetricks_wine if winetricks_wine and not proton.is_proton_path(wine_path) else wine_path
        create_prefix(prefix, wine_path=wine_bin, arch=arch, runner=runner)

    wine_system_config = config.system_config if config else runner.system_config
    disable_runtime = disable_runtime or wine_system_config["disable_runtime"]
    if use_lutris_runtime(wine_path=wineenv["WINE"], force_disable=disable_runtime) and not proton.is_proton_path(
        wine_path
    ):
        if WINE_DIR in wine_path:
            wine_root_path = os.path.dirname(os.path.dirname(wine_path))
        elif winetricks_wine and WINE_DIR in winetricks_wine:
            wine_root_path = os.path.dirname(os.path.dirname(winetricks_wine))
        else:
            wine_root_path = None
        wineenv["LD_LIBRARY_PATH"] = ":".join(
            runtime.get_paths(
                prefer_system_libs=wine_system_config["prefer_system_libs"],
                wine_path=wine_root_path,
            )
        )

    if overrides:
        wineenv["WINEDLLOVERRIDES"] = get_overrides_env(overrides)

    if proton_verb:
        wineenv["PROTON_VERB"] = proton_verb

    baseenv = runner.get_env(disable_runtime=disable_runtime)
    baseenv.update(wineenv)
    baseenv.update(env)

    if proton.is_proton_path(wine_path):
        proton.update_proton_env(wine_path, baseenv)

    command_parameters = []
    if proton.is_proton_path(wine_path):
        command_parameters.append(proton.get_umu_path())
        if winetricks_wine and wine_path not in winetricks_wine:
            command_parameters.append("winetricks")
    else:
        command_parameters.append(wine_path)

    if executable:
        command_parameters.append(executable)
    command_parameters += split_arguments(args)

    runner.prelaunch()

    if blocking:
        return system.execute(command_parameters, env=baseenv, cwd=working_dir)

    command = MonitoredCommand(
        command_parameters,
        runner=runner,
        env=baseenv,
        cwd=working_dir,
        include_processes=include_processes,
        exclude_processes=exclude_processes,
    )
    command.start()
    return command


# pragma pylint: enable=too-many-locals


def find_winetricks(env=None, system_winetricks=False):
    """Find winetricks path."""
    winetricks_path = os.path.join(settings.RUNTIME_DIR, "winetricks/winetricks")
    if system_winetricks or not system.path_exists(winetricks_path):
        winetricks_path = system.find_required_executable("winetricks")
        working_dir = None
    else:
        # We will use our own zenity if available, which is here, and it
        # also needs a data file in this directory. We have to set the
        # working_dir, so it will find the data file.
        working_dir = os.path.join(settings.RUNTIME_DIR, "winetricks")

        if not env:
            env = {}

        path = env.get("PATH", os.environ["PATH"])
        env["PATH"] = "%s:%s" % (working_dir, path)

    return (winetricks_path, working_dir, env)


def winetricks(
    app,
    prefix=None,
    arch=None,
    silent=True,
    wine_path=None,
    config=None,
    env=None,
    disable_runtime=False,
    system_winetricks=False,
    runner=None,
    proton_verb=None,
):
    """Execute winetricks."""
    winetricks_path, working_dir, env = find_winetricks(env, system_winetricks)

    if wine_path:
        winetricks_wine = wine_path
        if proton.is_proton_path(wine_path):
            protonfixes_path = os.path.join(proton.get_proton_path_by_path(wine_path), "protonfixes")
            if os.path.exists(protonfixes_path):
                winetricks_wine = os.path.join(protonfixes_path, "winetricks")
                winetricks_path = wine_path
                if not app:
                    silent = False
                    app = "--gui"
            else:
                logger.info("winetricks: Valve official Proton builds do not support winetricks.")
                return
    else:
        if not runner:
            runner = import_runner("wine")()
        winetricks_wine = runner.get_executable()

    if arch not in ("win32", "win64"):
        arch = detect_arch(prefix, winetricks_wine)
    args = app

    if str(silent).lower() in ("yes", "on", "true") and not proton.is_proton_path(wine_path):
        args = "-q " + args
    else:
        if proton.is_proton_path(wine_path):
            proton_verb = "waitforexitandrun"

    # Execute wineexec
    return wineexec(
        None,
        prefix=prefix,
        winetricks_wine=winetricks_wine,
        wine_path=winetricks_path,
        working_dir=working_dir,
        arch=arch,
        args=args,
        config=config,
        env=env,
        disable_runtime=disable_runtime,
        runner=runner,
        proton_verb=proton_verb,
    )


def winecfg(wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH, config=None, env=None, runner=None, proton_verb=None):
    """Execute winecfg."""

    if not wine_path:
        logger.debug("winecfg: Reverting to default wine")
        wine = import_runner("wine")
        wine_path = wine().get_executable()

    if proton.is_proton_path(wine_path):
        proton_verb = "waitforexitandrun"

    return wineexec(
        "winecfg.exe",
        prefix=prefix,
        winetricks_wine=wine_path,
        wine_path=wine_path,
        arch=arch,
        config=config,
        env=env,
        include_processes=["winecfg.exe"],
        runner=runner,
        proton_verb=proton_verb,
    )


def eject_disc(wine_path, prefix, proton_verb=None):
    """Use Wine to eject a drive"""

    if proton.is_proton_path(wine_path):
        proton_verb = "run"
    wineexec("eject", prefix=prefix, wine_path=wine_path, args="-a", proton_verb=proton_verb)


def install_cab_component(cabfile, component, wine_path=None, prefix=None, arch=None, proton_verb=None):
    """Install a component from a cabfile in a prefix"""

    if proton.is_proton_path(wine_path):
        proton_verb = "run"
    cab_installer = CabInstaller(prefix, wine_path=wine_path, arch=arch)
    files = cab_installer.extract_from_cab(cabfile, component)
    registry_files = cab_installer.get_registry_files(files)
    for registry_file, _arch in registry_files:
        set_regedit_file(registry_file, wine_path=wine_path, prefix=prefix, arch=_arch, proton_verb=proton_verb)
    cab_installer.cleanup()


def open_wine_terminal(terminal, wine_path, prefix, env, system_winetricks):
    winetricks_path, _working_dir, env = find_winetricks(env, system_winetricks)
    path_paths = [os.path.dirname(wine_path)]
    if proton.is_proton_path(wine_path):
        proton.update_proton_env(wine_path, env)
        umu_path = proton.get_umu_path()
        path_paths.insert(0, os.path.dirname(umu_path))
        wine_command = umu_path + " wine"
    else:
        wine_command = wine_path

    aliases = {
        "wine": wine_command,
        "winecfg": wine_command + "cfg",
        "wineserver": wine_command + "server",
        "wineboot": wine_command + "boot",
        "winetricks": wine_command,
    }
    env["WINEPREFIX"] = prefix
    # Ensure scripts you run see the desired version of WINE too
    # by putting it on the PATH.

    path_paths.append(env.get("PATH", os.environ["PATH"]))
    path_paths = [p for p in path_paths if p]
    if path_paths:
        env["PATH"] = ":".join(path_paths)
    shell_command = get_shell_command(prefix, env, aliases)
    terminal = terminal or linux.get_default_terminal()
    system.spawn([terminal, "-e", shell_command])
