import os
from lutris.util.log import logger

def scan_folder(folder):
    """do a recursive browse of the folder string / list of string.
    return as a list with all file under this folder."""
    if isinstance(folder, list):
        folder_to_scan = folder
    elif isinstance(folder, str):
        folder_to_scan = [folder]
    else:
        raise BaseException

    file_scanned = []

    while len(folder_to_scan) > 0:
        selected = folder_to_scan[-1]
        selected = folder_to_scan.pop()
        for element in os.listdir(selected):
            complete_url = selected + "/" + element
            if os.path.isfile(complete_url):
                file_scanned.append(complete_url)
            elif os.path.isdir(complete_url):
                folder_to_scan.append(complete_url)
            else:
                logger.error("unknow type of file at %s", complete_url)

    return file_scanned
