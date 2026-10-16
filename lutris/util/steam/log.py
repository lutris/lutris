"""Steam log handling"""

# Standard Library
import os
import time


def _get_last_content_log(steam_data_dir: str) -> list[str]:
    """Return the last block from content_log.txt"""
    if not steam_data_dir:
        return []
    path = os.path.join(steam_data_dir, "logs/content_log.txt")
    blocks: list[list[str]] = [[]]
    blank_lines = 0
    try:
        with open(path, "r", encoding="utf-8") as logfile:
            for line in logfile:
                # Strip old logs: Steam separates each run from the previous one
                # with an empty line, and a second empty line in a row starts a new
                # block. We can't compare against "\r\n" here, since reading the
                # file in text mode has already turned those into "\n".
                if not line.strip():
                    blank_lines += 1
                    if blank_lines > 1 and blocks[-1]:
                        blocks.append([])
                    continue
                blank_lines = 0
                blocks[-1].append(line)
    except IOError:
        return []
    # Return the latest run, ignoring any separator left at the end of the file.
    return next((block for block in reversed(blocks) if block), [])


def get_app_log(steam_data_dir: str, appid: str, start_time: time.struct_time | None = None) -> list[str]:
    """Return all log entries related to appid from the latest Steam run.

    :param start_time: Time tuple, log entries older than this are dumped.
    """
    if start_time:
        start_time_str = time.strftime("%Y-%m-%d %T", start_time)

    app_log = []
    for line in _get_last_content_log(steam_data_dir):
        if start_time and line[1:20] < start_time_str:
            continue
        if " %s " % appid in line[22:]:
            app_log.append(line)
    return app_log


def get_app_state_log(steam_data_dir: str, appid: str, start_time: time.struct_time | None = None) -> list[str]:
    """Return state entries for appid from latest block in content_log.txt.

    "Fully Installed, Running" means running.
    "Fully Installed" means stopped.

    :param start_time: Time tuple, log entries older than this are dumped.
    """
    state_log = []
    for line in get_app_log(steam_data_dir, appid, start_time):
        line = line.split(" : ")
        if len(line) == 1:
            continue
        if line[0].endswith("state changed"):
            state_log.append(line[1][:-2])
    return state_log
