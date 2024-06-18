"""Wine commands for installers"""

# pylint: disable=too-many-arguments
import os
import shlex
import time
from gettext import gettext as _

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

GE_PROTON_LATEST = _("GE-Proton (Latest)")


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


def set_regedit_file(filename, wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH):
    """Apply a regedit file to the Windows registry."""
    if arch == "win64" and wine_path and system.path_exists(wine_path + "64"):
        # Use wine64 by default if set to a 64bit prefix. Using regular wine
        # will prevent some registry keys from being created. Most likely to be
        # a bug in Wine. see: https://github.com/lutris/lutris/issues/804
        wine_path = wine_path + "64"

    wineexec(
        "regedit",
        args="/S '%s'" % filename,
        wine_path=wine_path,
        prefix=prefix,
        arch=arch,
        blocking=True,
    )


def delete_registry_key(key, wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH):
    """Deletes a registry key from a Wine prefix"""
    wineexec(
        "regedit",
        args='/S /D "%s"' % key,
        wine_path=wine_path,
        prefix=prefix,
        arch=arch,
        blocking=True,
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

    if not proton.is_proton_path(wine_path):
        wineboot_path = os.path.join(os.path.dirname(wine_path), "wineboot")
        if not system.path_exists(wineboot_path):
            logger.error(
                "No wineboot executable found in %s, " "your wine installation is most likely broken",
                wine_path,
            )
            return

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

    if not proton.is_proton_path(wine_path):
        system.execute([wineboot_path], env=wineenv)
    else:
        wineenv["GAMEID"] = proton.DEFAULT_GAMEID
        wineenv["UMU_LOG"] = "debug"
        wineenv["WINEARCH"] = "win64"
        wineenv["PROTONPATH"] = proton.get_proton_path_from_bin(wine_path)
        command = MonitoredCommand([proton.get_umu_path(), "createprefix"], env=wineenv)
        command.start()

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
    steam_data_dir = os.path.expanduser("~/.local/share/Steam/compatibilitytools.d")
    if not env:
        env = {"WINEARCH": arch, "WINEPREFIX": prefix}
    if wine_path == GE_PROTON_LATEST and os.path.exists(f"{steam_data_dir}/UMU-Latest"):
        proton_version = os.path.realpath(f"{steam_data_dir}/UMU-Latest")
        command = [os.path.join(proton_version, "files", "bin", "wineserver"), "-k"]
        env["GAMEID"] = proton.DEFAULT_GAMEID
        env["WINEPREFIX"] = prefix
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

    # Create prefix if necessary
    if arch not in ("win32", "win64"):
        arch = detect_arch(prefix, wine_path)
    if not is_prefix_directory(prefix):
        wine_bin = winetricks_wine if winetricks_wine else wine_path
        create_prefix(prefix, wine_path=wine_bin, arch=arch, runner=runner)

    wineenv = {"WINEARCH": arch}
    if winetricks_wine:
        wineenv["WINE"] = winetricks_wine
    else:
        wineenv["WINE"] = wine_path

    if prefix:
        wineenv["WINEPREFIX"] = prefix

    wine_system_config = config.system_config if config else runner.system_config
    disable_runtime = disable_runtime or wine_system_config["disable_runtime"]
    if use_lutris_runtime(wine_path=wineenv["WINE"], force_disable=disable_runtime):
        if WINE_DIR in wine_path:
            wine_root_path = os.path.dirname(os.path.dirname(wine_path))
        elif WINE_DIR in winetricks_wine:
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

    # TODO: Move this to somewhere that a reference to the game object
    if proton.is_proton_path(wine_path):
        game = None
        wineenv["GAMEID"] = proton.get_game_id(game)

        if wine_path == GE_PROTON_LATEST:
            wine_path = proton.get_umu_path()
        else:
            wineenv["PROTONPATH"] = proton.get_proton_path_from_bin(wine_path)
        locale = env.get("LC_ALL")
        host_locale = env.get("HOST_LC_ALL")
        if locale and not host_locale:
            wineenv["HOST_LC_ALL"] = locale

    baseenv = runner.get_env(disable_runtime=disable_runtime)
    baseenv.update(wineenv)
    baseenv.update(env)

    command_parameters = [wine_path]
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
):
    """Execute winetricks."""
    winetricks_path, working_dir, env = find_winetricks(env, system_winetricks)

    if wine_path:
        winetricks_wine = wine_path
    else:
        if not runner:
            runner = import_runner("wine")()
        winetricks_wine = runner.get_executable()
    # We only need to perform winetricks if not using umu/proton. umu uses protonfixes
    if proton.is_proton_path(wine_path):
        logger.warning("Winetricks is currently not supported with Proton")
        return
    if arch not in ("win32", "win64"):
        arch = detect_arch(prefix, winetricks_wine)
    args = app
    if str(silent).lower() in ("yes", "on", "true"):
        args = "--unattended " + args

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
    )


def winecfg(wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH, config=None, env=None, runner=None):
    """Execute winecfg."""
    if not wine_path:
        logger.debug("winecfg: Reverting to default wine")
        wine = import_runner("wine")
        wine_path = wine().get_executable()

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
    )


def eject_disc(wine_path, prefix):
    """Use Wine to eject a drive"""
    wineexec("eject", prefix=prefix, wine_path=wine_path, args="-a")


def install_cab_component(cabfile, component, wine_path=None, prefix=None, arch=None):
    """Install a component from a cabfile in a prefix"""
    cab_installer = CabInstaller(prefix, wine_path=wine_path, arch=arch)
    files = cab_installer.extract_from_cab(cabfile, component)
    registry_files = cab_installer.get_registry_files(files)
    for registry_file, _arch in registry_files:
        set_regedit_file(registry_file, wine_path=wine_path, prefix=prefix, arch=_arch)
    cab_installer.cleanup()


def open_wine_terminal(terminal, wine_path, prefix, env, system_winetricks):
    winetricks_path, _working_dir, env = find_winetricks(env, system_winetricks)
    aliases = {
        "wine": wine_path,
        "winecfg": wine_path + "cfg",
        "wineserver": wine_path + "server",
        "wineboot": wine_path + "boot",
        "winetricks": winetricks_path,
    }
    env["WINEPREFIX"] = prefix
    # Ensure scripts you run see the desired version of WINE too
    # by putting it on the PATH.
    wine_directory = os.path.split(wine_path)[0]
    if wine_directory:
        path = env.get("PATH", os.environ["PATH"])
        env["PATH"] = "%s:%s" % (wine_directory, path)
    shell_command = get_shell_command(prefix, env, aliases)
    terminal = terminal or linux.get_default_terminal()
    system.spawn([terminal, "-e", shell_command])
