
import os
import shutil

from lutris import api
from lutris.settings import RUNTIME_DIR
from lutris.util.extract import extract_archive
from lutris.util.http import download_file
from lutris.util.log import logger
from lutris.util.system import create_folder, delete_folder, execute


def update_shader_cache(game):
    state_cache_path = game.config.system_config["env"]["DXVK_STATE_CACHE_PATH"]
    if not os.path.exists(state_cache_path):
        logger.warning("%s is not a valid path", state_cache_path)
        return False
    game_details = api.get_game_details(game.slug)
    if not game_details.get("shaders"):
        logger.debug("No shaders for %s", game)
        return False
    last_updated_local = game.config.game_config.get("dxvk_cache_updated_at")
    most_recent_update = None
    shader_url = None
    for shader in game_details["shaders"]:
        if not most_recent_update or most_recent_update < shader["updated_at"]:
            shader_url = shader["url"]
            most_recent_update = shader["updated_at"]
    if last_updated_local and last_updated_local >= most_recent_update:
        logger.debug("Cache up to date")
        return False
    shader_merge_path = os.path.join(state_cache_path, "dxvk-state-cache")
    create_folder(shader_merge_path)
    shader_archive_path = os.path.join(shader_merge_path, os.path.basename(shader_url))
    download_file(shader_url, shader_archive_path)
    extract_archive(shader_archive_path, to_directory=shader_merge_path)
    try:
        remote_cache_path = [
            shader_file for shader_file in os.listdir(shader_merge_path)
            if shader_file.endswith(".dxvk-cache")
        ][0]
    except IndexError:
        logger.error("Cache path not found")
        return False
    cache_file_name = os.path.basename(remote_cache_path)
    local_cache_path = os.path.join(state_cache_path, cache_file_name)
    if not os.path.exists(local_cache_path):
        shutil.copy(remote_cache_path, state_cache_path)
    else:
        local_copy_path = os.path.join(shader_merge_path, "Local.dxvk-cache")
        output_path = os.path.join(shader_merge_path, "output.dxvk-cache")
        shutil.copy(local_cache_path, local_copy_path)
        state_merge_tool_path = os.path.join(RUNTIME_DIR, "dxvk-cache-tool/dxvk_cache_tool")
        if not os.path.exists(state_merge_tool_path):
            logger.error("dxvk_cache_tool not present")
            return False
        execute([
            state_merge_tool_path,
            remote_cache_path,
            local_copy_path
        ], cwd=shader_merge_path)
        if not os.path.exists(output_path):
            logger.error("Merging of shader failed")
        shutil.copy(output_path, local_cache_path)
    delete_folder(shader_merge_path)
    game.config.game_level["game"]["dxvk_cache_updated_at"] = most_recent_update
    game.config.save()
