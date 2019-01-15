"""Wine commands for installers"""
# pylint: disable=too-many-arguments
import os
import shlex
import time

from lutris import runtime, settings
from lutris.config import LutrisConfig
from lutris.runners import import_runner
from lutris.command import MonitoredCommand
from lutris.util import datapath, system
from lutris.util.log import logger
from lutris.util.wine.wine import (
    WINE_DIR,
    WINE_DEFAULT_ARCH,
    detect_arch,
    detect_prefix_arch,
    get_overrides_env,
    get_real_executable,
    use_lutris_runtime,
)
from lutris.util.wine.prefix import WinePrefixManager


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
    with open(reg_path, "w") as reg_file:
        reg_file.write(
            'REGEDIT4\n\n[%s]\n"%s"=%s\n' % (path, key, formatted_value[type])
        )
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
        overrides={},
        install_gecko=None,
        install_mono=None,
):
    """Create a new Wine prefix."""
    if not prefix:
        raise ValueError("No Wine prefix path given")
    logger.info("Creating a %s prefix in %s", arch, prefix)

    # Avoid issue of 64bit Wine refusing to create win32 prefix
    # over an existing empty folder.
    if os.path.isdir(prefix) and not os.listdir(prefix):
        os.rmdir(prefix)

    if not wine_path:
        wine = import_runner("wine")
        wine_path = wine().get_executable()
    if not wine_path:
        logger.error("Wine not found, can't create prefix")
        return
    wineboot_path = os.path.join(os.path.dirname(wine_path), "wineboot")
    if not system.path_exists(wineboot_path):
        logger.error(
            "No wineboot executable found in %s, "
            "your wine installation is most likely broken",
            wine_path,
        )
        return

    if install_gecko == "False":
        overrides["mshtml"] = "disabled"
    if install_mono == "False":
        overrides["mscoree"] = "disabled"

    wineenv = {
        "WINEARCH": arch,
        "WINEPREFIX": prefix,
        "WINEDLLOVERRIDES": get_overrides_env(overrides),
    }

    system.execute([wineboot_path], env=wineenv)
    for loop_index in range(50):
        time.sleep(0.25)
        if system.path_exists(os.path.join(prefix, "user.reg")):
            break
        if loop_index == 20:
            logger.warning("Wine prefix creation is taking longer than expected...")
    if not os.path.exists(os.path.join(prefix, "user.reg")):
        logger.error(
            "No user.reg found after prefix creation. " "Prefix might not be valid"
        )
        return
    logger.info("%s Prefix created in %s", arch, prefix)
    prefix_manager = WinePrefixManager(prefix)
    prefix_manager.setup_defaults()
    if 'steamapps/common' in prefix.lower():
        from lutris.runners.winesteam import winesteam
        runner = winesteam()
        logger.info("Transfering Steam information from default prefix to new prefix")
        dest_path = '/tmp/steam.reg'
        default_prefix = runner.get_default_prefix(runner.default_arch)
        wineexec(
            "regedit",
            args=r"/E '%s' 'HKEY_CURRENT_USER\Software\Valve\Steam'" % dest_path,
            prefix=default_prefix
        )
        set_regedit_file(
            dest_path,
            wine_path=wine_path,
            prefix=prefix,
            arch=arch
        )
        os.remove(dest_path)
        steam_drive_path = os.path.join(prefix, 'dosdevices', 's:')
        if not system.path_exists(steam_drive_path):
            logger.info("Linking Steam default prefix to drive S:")
            os.symlink(os.path.join(default_prefix, 'drive_c'), steam_drive_path)


def winekill(prefix, arch=WINE_DEFAULT_ARCH, wine_path=None, env=None, initial_pids=None):
    """Kill processes in Wine prefix."""

    initial_pids = initial_pids or []

    if not wine_path:
        wine = import_runner("wine")
        wine_path = wine().get_executable()
    wine_root = os.path.dirname(wine_path)
    if not env:
        env = {"WINEARCH": arch, "WINEPREFIX": prefix}
    command = [os.path.join(wine_root, "wineserver"), "-k"]

    logger.debug("Killing all wine processes: %s", command)
    logger.debug("\tWine prefix: %s", prefix)
    logger.debug("\tWine arch: %s", arch)
    if initial_pids:
        logger.debug("\tInitial pids: %s", initial_pids)

    system.execute(command, env=env, quiet=True)

    logger.debug("Waiting for wine processes to terminate")
    # Wineserver needs time to terminate processes
    num_cycles = 0
    while True:
        num_cycles += 1
        running_processes = [
            pid for pid in initial_pids if system.path_exists("/proc/%s" % pid)
        ]

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


def wineexec(
        executable,
        args="",
        wine_path=None,
        prefix=None,
        arch=None,  # pylint: disable=too-many-locals
        working_dir=None,
        winetricks_wine="",
        blocking=False,
        config=None,
        include_processes=[],
        exclude_processes=[],
        disable_runtime=False,
        env={},
        overrides=None,
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

    Returns:
        Process results if the process is running in blocking mode or
        MonitoredCommand instance otherwise.
    """
    executable = str(executable) if executable else ""
    include_processes = shlex.split(include_processes or "")
    exclude_processes = shlex.split(exclude_processes or "")
    if not wine_path:
        wine = import_runner("wine")
        wine_path = wine().get_executable()
    if not wine_path:
        raise RuntimeError("Wine is not installed")

    if not working_dir:
        if os.path.isfile(executable):
            working_dir = os.path.dirname(executable)

    executable, _args, working_dir = get_real_executable(executable, working_dir)
    if _args:
        args = '{} "{}"'.format(_args[0], _args[1])

    # Create prefix if necessary
    if arch not in ("win32", "win64"):
        arch = detect_arch(prefix, wine_path)
    if not detect_prefix_arch(prefix):
        wine_bin = winetricks_wine if winetricks_wine else wine_path
        create_prefix(prefix, wine_path=wine_bin, arch=arch)

    wineenv = {"WINEARCH": arch}
    if winetricks_wine:
        wineenv["WINE"] = winetricks_wine
    else:
        wineenv["WINE"] = wine_path

    if prefix:
        wineenv["WINEPREFIX"] = prefix

    wine_config = config or LutrisConfig(runner_slug="wine")
    disable_runtime = disable_runtime or wine_config.system_config["disable_runtime"]
    if use_lutris_runtime(wine_path=wineenv["WINE"], force_disable=disable_runtime):
        if WINE_DIR in wine_path:
            wine_root_path = os.path.dirname(os.path.dirname(wine_path))
        elif WINE_DIR in winetricks_wine:
            wine_root_path = os.path.dirname(os.path.dirname(winetricks_wine))
        else:
            wine_root_path = None
        wineenv["LD_LIBRARY_PATH"] = ":".join(
            runtime.get_paths(
                prefer_system_libs=wine_config.system_config["prefer_system_libs"],
                wine_path=wine_root_path,
            )
        )

    if overrides:
        wineenv["WINEDLLOVERRIDES"] = get_overrides_env(overrides)

    wineenv.update(env)

    command_parameters = [wine_path]
    if executable:
        command_parameters.append(executable)
    command_parameters += shlex.split(args)
    if blocking:
        return system.execute(command_parameters, env=wineenv, cwd=working_dir)
    wine = import_runner("wine")
    command = MonitoredCommand(
        command_parameters,
        runner=wine(),
        env=wineenv,
        cwd=working_dir,
        include_processes=include_processes,
        exclude_processes=exclude_processes,
    )
    command.start()
    return command


def winetricks(
        app,
        prefix=None,
        arch=None,
        silent=True,
        wine_path=None,
        config=None,
        disable_runtime=False,
):
    """Execute winetricks."""
    winetricks_path = os.path.join(settings.RUNTIME_DIR, "winetricks/winetricks")
    if not system.path_exists(winetricks_path):
        logger.warning(
            "Could not find local winetricks install, falling back to bundled version"
        )
        winetricks_path = os.path.join(datapath.get(), "bin/winetricks")
    if wine_path:
        winetricks_wine = wine_path
    else:
        wine = import_runner("wine")
        winetricks_wine = wine().get_executable()
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
        arch=arch,
        args=args,
        config=config,
        disable_runtime=disable_runtime,
    )


def winecfg(wine_path=None, prefix=None, arch=WINE_DEFAULT_ARCH, config=None):
    """Execute winecfg."""
    if not wine_path:
        logger.debug("winecfg: Reverting to default wine")
        wine = import_runner("wine")
        wine_path = wine().get_executable()

    winecfg_path = os.path.join(os.path.dirname(wine_path), "winecfg")
    logger.debug("winecfg: %s", winecfg_path)

    return wineexec(
        None,
        prefix=prefix,
        winetricks_wine=winecfg_path,
        wine_path=winecfg_path,
        arch=arch,
        config=config,
        include_processes=["winecfg.exe"],
    )


def joycpl(wine_path=None, prefix=None, config=None):
    """Execute Joystick control panel."""
    logger.debug("What is config and why do we need it? %s", config)
    arch = detect_arch(prefix, wine_path)
    wineexec("control", prefix=prefix, wine_path=wine_path, arch=arch, args="joy.cpl")


def eject_disc(wine_path, prefix):
    """Use Wine to eject a drive"""
    wineexec("eject", prefix=prefix, wine_path=wine_path, args="-a")
