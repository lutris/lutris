import os
import tarfile
import zipfile
import gzip
from lutris.util.log import logger


def extract_archive(path, to_directory='.'):
    path = os.path.abspath(path)
    logger.debug("Extracting %s to %s", path, to_directory)
    if path.endswith('.zip'):
        opener, mode = zipfile.ZipFile, 'r'
    elif path.endswith('.tar.gz') or path.endswith('.tgz'):
        opener, mode = tarfile.open, 'r:gz'
    elif path.endswith('.tar.bz2') or path.endswith('.tbz'):
        opener, mode = tarfile.open, 'r:bz2'
    else:
        raise ValueError(
            "Could not extract `%s` as no appropriate extractor is found"
            % path)
    cwd = os.getcwd()
    os.chdir(to_directory)
    handler = opener(path, mode)
    handler.extractall()
    handler.close()
    os.chdir(cwd)


def decompress_gz(file_path):
    """Decompress a gzip file"""
    if file_path.endswith('.gz'):
        dest_path = file_path[:-3]
    else:
        raise ValueError("unsupported file type")

    f = gzip.open(file_path, 'rb')
    file_content = f.read()
    f.close()

    dest_file = open(dest_path, 'wb')
    dest_file.write(file_content)
    dest_file.close()

    return dest_path
