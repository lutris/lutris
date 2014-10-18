import os
import shutil
import tarfile
import zipfile
import gzip
import subprocess
from lutris.util.system import merge_folders
from lutris.util.log import logger


def extract_archive(path, to_directory='.', merge_single=True, extractor=None):
    path = os.path.abspath(path)
    logger.debug("Extracting %s to %s", path, to_directory)
    if path.endswith('.zip') or extractor == 'zip':
        opener, mode = zipfile.ZipFile, 'r'
    elif(path.endswith('.tar.gz') or path.endswith('.tgz')
         or extractor == 'tgz'):
        opener, mode = tarfile.open, 'r:gz'
    elif path.endswith('.gz') or extractor == 'gzip':
        decompress_gz(path, to_directory)
        return
    elif(path.endswith('.tar.bz2') or path.endswith('.tbz')
         or extractor == 'bz2'):
        opener, mode = tarfile.open, 'r:bz2'
    else:
        raise RuntimeError(
            "Could not extract `%s` as no appropriate extractor is found"
            % path)
    destination = temp_dir = os.path.join(to_directory, ".lutris_extracted")
    handler = opener(path, mode)
    handler.extractall(destination)
    handler.close()
    if merge_single:
        extracted = os.listdir(destination)
        if len(extracted) == 1:
            destination = os.path.join(destination, extracted[0])

    if os.path.isfile(destination):
        shutil.move(destination, to_directory)
        os.removedirs(temp_dir)
    else:
        for f in os.listdir(destination):
            logger.debug("Moving element %s of archive", f)
            source_path = os.path.join(destination, f)
            destination_path = os.path.join(to_directory, f)
            if os.path.exists(destination_path):
                logger.warning("%s already exists", destination_path)
                if os.path.isfile(destination_path):
                    os.remove(destination_path)
                    shutil.move(source_path, destination_path)
                elif os.path.isdir(destination_path):
                    merge_folders(source_path, destination_path)
            else:
                shutil.move(source_path, destination_path)
        shutil.rmtree(destination)
    logger.debug("Finished extracting %s", path)


def decompress_gz(file_path, dest_path=None):
    """Decompress a gzip file"""
    if dest_path:
        dest_filename = os.path.join(dest_path,
                                     os.path.basename(file_path[:-3]))
    else:
        dest_filename = file_path[:-3]

    gzipped_file = gzip.open(file_path, 'rb')
    file_content = gzipped_file.read()
    gzipped_file.close()

    dest_file = open(dest_filename, 'wb')
    dest_file.write(file_content)
    dest_file.close()

    return dest_path


def unzip(filename, dest=None):
    """Unzips a file"""
    command = ["unzip", '-o', filename]
    if dest:
        command = command + ['-d', dest]
    subprocess.call(command)


def unrar(filename):
    """Unrar a file"""

    subprocess.call(["unrar", "x", filename])


def untar(filename, dest=None, method='gzip'):
    """Untar a file"""
    cwd = os.getcwd()
    if dest is None or not os.path.exists(dest):
        dest = cwd
    logger.debug("Will extract to %s" % dest)
    os.chdir(dest)
    if method == 'gzip':
        compression_flag = 'z'
    elif method == 'bzip2':
        compression_flag = 'j'
    else:
        compression_flag = ''
    cmd = "tar x%sf %s" % (compression_flag, filename)
    logger.debug(cmd)
    subprocess.Popen(cmd, shell=True)
    os.chdir(cwd)
