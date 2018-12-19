"""Hardware driver related utilities"""
import os


def get_nvidia_driver_info():
    """Return information about NVidia drivers"""
    with open("/proc/driver/nvidia/version") as version_file:
        content = version_file.readlines()
    nvrm_version = content[0].split(': ')[1].strip().split()
    gcc_version = content[1].split(': ')[1].strip().split()

    return {
        'nvrm': {
            'vendor': nvrm_version[0],
            'platform': nvrm_version[1],
            'arch': nvrm_version[2],
            'version': nvrm_version[5],
            'date': ' '.join(nvrm_version[6:])
        },
        'gcc': {
            'version': gcc_version[2],
            'platform': ' '.join(gcc_version[3:]).strip('()')
        }
    }


def get_nvidia_gpu_ids():
    """Return the list of Nvidia GPUs"""
    return os.listdir("/proc/driver/nvidia/gpus")


def get_nvidia_gpu_info(gpu_id):
    """Return details about a GPU"""
    with open("/proc/driver/nvidia/gpus/%s/information" % gpu_id) as info_file:
        content = info_file.readlines()
    infos = {}
    for line in content:
        key, value = line.split(":", 1)
        infos[key] = value.strip()
    return infos
