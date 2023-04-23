"""Transform runner parameters to data usable for runtime execution"""
import os
import shlex
import stat

from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger


def get_mangohud_conf(system_config):
    """Return correct launch arguments and environment variables for Mangohud."""
    # The environment variable should be set to 0 on gamescope, otherwise the game will crash
    mangohud_val = "0" if system_config.get("gamescope") else "1"
    if system_config.get("mangohud") and system.find_executable("mangohud"):
        return ["mangohud"], {"MANGOHUD": mangohud_val, "MANGOHUD_DLSYM": "1"}
    return None, None


def get_launch_parameters(runner, gameplay_info):
    system_config = runner.system_config
    launch_arguments = gameplay_info["command"]
    env = {
        "DISABLE_LAYER_AMD_SWITCHABLE_GRAPHICS_1": "1"
    }

    # Steam compatibility
    if os.environ.get("SteamAppId"):
        logger.info("Game launched from steam (AppId: %s)", os.environ["SteamAppId"])
        env["LC_ALL"] = ""

    # Set correct LC_ALL depending on user settings
    if system_config["locale"] != "":
        env["LC_ALL"] = system_config["locale"]

    # Optimus
    optimus = system_config.get("optimus")
    if optimus == "primusrun" and system.find_executable("primusrun"):
        launch_arguments.insert(0, "primusrun")
    elif optimus == "optirun" and system.find_executable("optirun"):
        launch_arguments.insert(0, "virtualgl")
        launch_arguments.insert(0, "-b")
        launch_arguments.insert(0, "optirun")
    elif optimus == "pvkrun" and system.find_executable("pvkrun"):
        launch_arguments.insert(0, "pvkrun")

    # MangoHud
    mango_args, mango_env = get_mangohud_conf(system_config)
    if mango_args:
        launch_arguments = mango_args + launch_arguments
        env.update(mango_env)

    # Libstrangle
    fps_limit = system_config.get("fps_limit") or ""
    if fps_limit:
        strangle_cmd = system.find_executable("strangle")
        if strangle_cmd:
            launch_arguments = [strangle_cmd, fps_limit] + launch_arguments
        else:
            logger.warning("libstrangle is not available on this system, FPS limiter disabled")

    prefix_command = system_config.get("prefix_command") or ""
    if prefix_command:
        launch_arguments = shlex.split(os.path.expandvars(prefix_command)) + launch_arguments

    single_cpu = system_config.get("single_cpu") or False
    if single_cpu:
        limit_cpu_count = system_config.get("limit_cpu_count")
        if limit_cpu_count and limit_cpu_count.isnumeric():
            limit_cpu_count = int(limit_cpu_count)
        else:
            limit_cpu_count = 1

        limit_cpu_count = max(1, limit_cpu_count)
        logger.info("The game will run on %d CPU core(s)", limit_cpu_count)
        launch_arguments.insert(0, "0-%d" % (limit_cpu_count - 1))
        launch_arguments.insert(0, "-c")
        launch_arguments.insert(0, "taskset")

    env.update(runner.get_env())

    env.update(gameplay_info.get("env") or {})

    # Set environment variables dependent on gameplay info

    # LD_PRELOAD
    ld_preload = gameplay_info.get("ld_preload")
    if ld_preload:
        env["LD_PRELOAD"] = ld_preload

    # LD_LIBRARY_PATH
    game_ld_library_path = gameplay_info.get("ld_library_path")
    if game_ld_library_path:
        ld_library_path = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [
            game_ld_library_path, ld_library_path]))

    # Feral gamemode
    gamemode = system_config.get("gamemode") and LINUX_SYSTEM.gamemode_available()
    if gamemode:
        launch_arguments.insert(0, "gamemoderun")

    # Gamescope
    gamescope = system_config.get("gamescope") and system.find_executable("gamescope")
    if gamescope:
        launch_arguments = get_gamescope_args(launch_arguments, system_config)

    return launch_arguments, env


def get_gamescope_args(launch_arguments, system_config):
    """Insert gamescope at the start of the launch arguments"""
    launch_arguments.insert(0, "--")
    if system_config.get("gamescope_force_grab_cursor"):
        launch_arguments.insert(0, "--force-grab-cursor")
    if system_config.get("gamescope_fsr_sharpness"):
        gamescope_fsr_sharpness = system_config["gamescope_fsr_sharpness"]
        launch_arguments.insert(0, gamescope_fsr_sharpness)
        launch_arguments.insert(0, "--fsr-sharpness")
        launch_arguments.insert(0, "-U")
    if system_config.get("gamescope_flags"):
        gamescope_flags = system_config["gamescope_flags"]
        launch_arguments.insert(0, gamescope_flags)
    if system_config.get("gamescope_window_mode"):
        gamescope_window_mode = system_config["gamescope_window_mode"]
        launch_arguments.insert(0, gamescope_window_mode)
    if system_config.get("gamescope_fps_limiter"):
        gamescope_fps_limiter = system_config["gamescope_fps_limiter"]
        launch_arguments.insert(0, gamescope_fps_limiter)
        launch_arguments.insert(0, "-r")
    if system_config.get("gamescope_output_res"):
        output_width, output_height = system_config["gamescope_output_res"].lower().split("x")
        launch_arguments.insert(0, output_height)
        launch_arguments.insert(0, "-H")
        launch_arguments.insert(0, output_width)
        launch_arguments.insert(0, "-W")
    if system_config.get("gamescope_game_res"):
        game_width, game_height = system_config["gamescope_game_res"].lower().split("x")
        launch_arguments.insert(0, game_height)
        launch_arguments.insert(0, "-h")
        launch_arguments.insert(0, game_width)
        launch_arguments.insert(0, "-w")
    launch_arguments.insert(0, "gamescope")
    return launch_arguments


def export_bash_script(runner, gameplay_info, script_path):
    """Convert runner configuration into a bash script"""
    runner.prelaunch()
    command, env = get_launch_parameters(runner, gameplay_info)
    # Override TERM otherwise the script might not run
    env["TERM"] = "xterm"
    script_content = "#!/bin/bash\n\n\n"

    script_content += "# Environment variables\n"

    for name, value in env.items():
        script_content += 'export %s="%s"\n' % (name, value)

    if "working_dir" in gameplay_info:
        script_content += "\n# Working Directory\n"
        script_content += "cd %s\n" % shlex.quote(gameplay_info["working_dir"])

    script_content += "\n# Command\n"
    script_content += " ".join([shlex.quote(c) for c in command])

    with open(script_path, "w", encoding='utf-8') as script_file:
        script_file.write(script_content)

    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
