"""Vulkan helper module"""
import os
import re
from enum import Enum

class vulkan_available(Enum):
    NONE = 0
    THIRTY_TWO = 1
    SIXTY_FOUR = 2
    ALL = 3

def search_for_file(directory):
    if os.path.isdir(directory):
        pattern = re.compile(r'^libvulkan\.so')
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        files = [os.path.join(directory, f) for f in files if pattern.search(f)]
        if files:
            return True
    return False

def vulkan_check():
    vulkan_lib = search_for_file("/usr/lib")
    vulkan_lib32 = search_for_file("/usr/lib32")
    vulkan_lib_multi = search_for_file("/usr/lib/x86_64-linux-gnu")
    vulkan_lib32_multi =  search_for_file("/usr/lib32/i386-linux-gnu")
    has_32_bit = vulkan_lib32 or vulkan_lib32_multi
    has_64_bit = vulkan_lib or vulkan_lib_multi

    if not (has_64_bit or has_32_bit):
        return vulkan_available.NONE
    if has_64_bit and not has_32_bit:
        return vulkan_available.SIXTY_FOUR
    if not has_64_bit and has_32_bit:
        return vulkan_available.THIRTY_TWO
    return vulkan_available.ALL
