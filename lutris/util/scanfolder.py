import os

def scan_folder(folder):
    """do a recursive browse of the folder string / list of string. return as a list with all file under this folder."""
    if type(folder) == list:
        folderToScan = folder
    elif type(folder) == str:
        folderToScan = [folder]
    else:
        raise BaseException

    fileScanned = []

    while len(folderToScan) > 0:
        selected = folderToScan[-1]
        selected = folderToScan.pop()
        for element in os.listdir(selected):
            completeURL = selected + "/" + element
            if os.path.isfile(completeURL):
                fileScanned.append(completeURL)
            elif os.path.isdir(completeURL):
                folderToScan.append(completeURL)
            else:
                raise

    return fileScanned
