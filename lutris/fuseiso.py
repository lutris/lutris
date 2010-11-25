
from subprocess import Popen, PIPE, STDOUT

def is_fuseiso_installed():
    fuseiso_command = Popen(["which","fuseiso"],
                            stdout=PIPE).stdout
    fuseiso_is_installed = fuseiso_command.readline()
    if "fuseiso" in fuseiso_is_installed:
        logging.debug("fuseiso is installed")
        return True
    else:
        logging.debug("fuseiso not here, problems ahead")
    	return False

def fuseiso_mount(iso, dest):
    """Mount an iso file with fuseiso"""
    fuseiso_command = Popen(["fuseiso", iso, dest],
                            stdout=PIPE, stderr=STDOUT)
    return dest

