import subprocess
import unittest
from unittest.mock import patch

from lutris.util.graphics import gpu

VULKANINFO_SUMMARY = """\
==========
VULKANINFO
==========

Devices:
========
GPU0:
	apiVersion         = 1.4.329
	vendorID           = 0x10de
	deviceID           = 0x2684
	deviceName         = NVIDIA GeForce RTX 4090
	deviceUUID         = 12345678-1234-1234-1234-123456789abc
GPU1:
	apiVersion         = 1.4.318
	vendorID           = 0x8086
	deviceID           = 0xa780
	deviceName         = Intel(R) Graphics (RPL-S)
	deviceUUID         = 8086a780-0000-0000-0000-000000000000
"""

GPU_INFOS = {
    "card0": {"DRIVER": "nvidia", "PCI_ID": "10DE:2684", "PCI_SUBSYS_ID": "", "PCI_SLOT_NAME": "0000:01:00.0"},
    "card1": {"DRIVER": "i915", "PCI_ID": "8086:A780", "PCI_SUBSYS_ID": "", "PCI_SLOT_NAME": "0000:00:02.0"},
}


def make_gpu(card):
    with (
        patch.object(gpu.GPU, "get_gpu_info", return_value=GPU_INFOS[card]),
        patch.object(gpu.GPU, "get_icd_files", return_value="/usr/share/vulkan/icd.d/%s_icd.json" % card),
    ):
        return gpu.GPU(card)


@patch.object(gpu, "VULKANINFO_PATH", "/usr/bin/vulkaninfo")
@patch.object(gpu.GPU, "get_lspci_name", return_value="lspci name")
class TestVulkaninfo(unittest.TestCase):
    def setUp(self):
        gpu.read_vulkaninfo_summary.cache_clear()

    def tearDown(self):
        gpu.read_vulkaninfo_summary.cache_clear()

    def test_vulkaninfo_runs_once_for_all_gpus(self, _lspci):
        with patch.object(gpu.system, "read_process_output", return_value=VULKANINFO_SUMMARY) as read_output:
            nvidia = make_gpu("card0")
            intel = make_gpu("card1")
        self.assertEqual(read_output.call_count, 1)
        self.assertEqual(nvidia.name, "NVIDIA GeForce RTX 4090")
        self.assertEqual(nvidia.device_uuid, "12345678123412341234123456789abc")
        self.assertEqual(intel.name, "Intel(R) Graphics (RPL-S)")

    def test_empty_output_retries_with_icd_files(self, _lspci):
        with patch.object(gpu.system, "read_process_output", side_effect=["", VULKANINFO_SUMMARY]) as read_output:
            nvidia = make_gpu("card0")
        self.assertEqual(read_output.call_count, 2)
        self.assertEqual(
            read_output.call_args.kwargs["env"]["VK_DRIVER_FILES"], "/usr/share/vulkan/icd.d/card0_icd.json"
        )
        self.assertEqual(nvidia.name, "NVIDIA GeForce RTX 4090")

    def test_failure_falls_back_to_lspci_and_is_not_retried(self, _lspci):
        error = subprocess.TimeoutExpired("vulkaninfo", 5)
        with patch.object(gpu.system, "read_process_output", side_effect=error) as read_output:
            nvidia = make_gpu("card0")
            intel = make_gpu("card1")
        self.assertEqual(read_output.call_count, 1)
        self.assertEqual(nvidia.name, "lspci name")
        self.assertIsNone(nvidia.device_uuid)
        self.assertEqual(intel.name, "lspci name")
