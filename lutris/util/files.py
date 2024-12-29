import os

from lutris.util.system import get_md5_hash


def get_folder_contents(target_directory: str, with_hash: bool = True) -> list:
    """Recursively iterate over a folder content and return its details"""
    folder_content = []
    for path, dir_names, file_names in os.walk(target_directory):
        for dir_name in dir_names:
            dir_path = os.path.join(path, dir_name)
            folder_content.append(
                {
                    "name": dir_path,
                    "date_created": int(os.path.getctime(dir_path)),
                    "date_modified": int(os.path.getmtime(dir_path)),
                    "date_accessed": int(os.path.getatime(dir_path)),
                    "type": "folder",
                }
            )
        for file_name in file_names:
            file_path = os.path.join(path, file_name)
            file_stats = os.stat(file_path)
            file_desc = {
                "name": file_path,
                "size": file_stats.st_size,
                "date_created": int(file_stats.st_ctime),
                "date_modified": int(file_stats.st_mtime),
                "date_accessed": int(file_stats.st_atime),
                "type": "file",
            }
            if with_hash:
                file_desc["md5_hash"] = get_md5_hash(file_path)
            folder_content.append(file_desc)
    return folder_content
