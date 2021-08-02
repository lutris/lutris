import os
import sys
import shutil


KNOWN_DIRS = [
    "ProgramData/Microsoft/Windows",
    "Program Files/Common Files/Microsoft Shared",
    "Program Files/Common Files/System",
    "Program Files/Internet Explorer",
    "Program Files/Windows Media Player",
    "Program Files/Windows NT",
    "windows",
]

def delete_known_dirs(prefix_path):
    for known_dir in KNOWN_DIRS:
        full_path = os.path.join(prefix_path, "drive_c", known_dir)
        if not os.path.exists(full_path):
            continue
        print("Deleting %s", full_path)
        shutil.rmtree(full_path)


def remove_empty_dirs(dirname):
    empty_folders = []
    for root, dirs, files in os.walk(dirname, topdown=True):
        print(root, files, dirs)
        if not files and not dirs:
            empty_folders.append(root)
    for folder in empty_folders:
        os.rmdir(folder)
    return empty_folders

dirname = sys.argv[1]
delete_known_dirs(dirname)
empty_folders = True
while empty_folders:
    empty_folders = remove_empty_dirs(dirname)
