"""Vulkan helper module"""
import os
from enum import Enum

class vulkan_available(Enum):
    NONE = 0
    THIRTY_TWO = 1
    SIXTY_FOUR = 2
    ALL = 3

def vulkan_check():
    vulkan_lib = os.path.isfile("/usr/lib/libvulkan.so")
    vulkan_lib32 = os.path.isfile("/usr/lib32/libvulkan.so")
    vulkan_lib_multi = os.path.isfile("/usr/lib/x86_64-linux-gnu/libvulkan.so")
    vulkan_lib32_multi = os.path.isfile("/usr/lib32/i386-linux-gnu/libvulkan.so")
    has_32_bit = vulkan_lib32 or vulkan_lib32_multi
    has_64_bit = vulkan_lib or vulkan_lib_multi

    if not (has_64_bit or has_32_bit):
        return vulkan_available.NONE
    if has_64_bit and not has_32_bit:
        return vulkan_available.SIXTY_FOUR
    if not has_64_bit and has_32_bit:
        return vulkan_available.THIRTY_TWO
    return vulkan_available.ALL
