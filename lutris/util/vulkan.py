"""Vulkan helper module"""
import os
import re
import subprocess
from enum import Enum

class vulkan_available(Enum):
    NONE = 0
    THIRTY_TWO = 1
    SIXTY_FOUR = 2
    ALL = 3

def vulkan_check():
    has_64_bit = False
    has_32_bit = False
    for line in subprocess.check_output(["ldconfig", "-p"]).splitlines():
        line = str(line)
        if 'libvulkan' in line:
            if not 'x86-64' in line:
                has_32_bit = True
            else:
                has_64_bit = True

    if not (has_64_bit or has_32_bit):
        return vulkan_available.NONE
    if has_64_bit and not has_32_bit:
        return vulkan_available.SIXTY_FOUR
    if not has_64_bit and has_32_bit:
        return vulkan_available.THIRTY_TWO
    return vulkan_available.ALL
