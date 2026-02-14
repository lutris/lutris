import io
import subprocess
import unittest
from unittest.mock import patch

from lutris.util.graphics import drivers, glxinfo

PROPRIETARY_MODULE_VERSION_FILE = """\
NVRM version: NVIDIA UNIX x86_64 Kernel Module  525.105.17  Tue Mar 28 18:02:59 UTC 2023
GCC version:  gcc version 11.3.0 (Ubuntu 11.3.0-1ubuntu1~22.04)
"""
PROPRIETARY_MODULE_OUTPUT = {
    "vendor": "NVIDIA",
    "platform": "UNIX",
    "arch": "x86_64",
    "version": "525.105.17",
    "date": "Tue Mar 28 18:02:59 UTC 2023",
}

OPEN_MODULE_VERSION_FILE = """\
NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  515.43.04  Release Build  (archlinux-builder@archlinux)
GCC version:  gcc version 12.1.0 (GCC)
"""
OPEN_MODULE_OUTPUT = {
    "vendor": "NVIDIA",
    "platform": "UNIX",
    "arch": "x86_64",
    "version": "515.43.04",
}
DRIVER_VERSION_FILES = (
    ("Proprietary", PROPRIETARY_MODULE_VERSION_FILE, PROPRIETARY_MODULE_OUTPUT),
    ("Open", OPEN_MODULE_VERSION_FILE, OPEN_MODULE_OUTPUT),
)
SAMPLE_GLXINFO_OUTPUT = """\
name of display: :0
display: :0  screen: 0
direct rendering: Yes
Memory info (GL_NVX_gpu_memory_info):
    Dedicated video memory: 6144 MB
    Total available memory: 6144 MB
    Currently available dedicated video memory: 3359 MB
OpenGL vendor string: NVIDIA Corporation
OpenGL renderer string: NVIDIA GeForce GTX 1660 SUPER/PCIe/SSE2
OpenGL core profile version string: 4.6.0 NVIDIA 525.105.17
OpenGL core profile shading language version string: 4.60 NVIDIA
OpenGL core profile context flags: (none)
OpenGL core profile profile mask: core profile

OpenGL version string: 4.6.0 NVIDIA 525.105.17
OpenGL shading language version string: 4.60 NVIDIA
OpenGL context flags: (none)
OpenGL profile mask: (none)

OpenGL ES profile version string: OpenGL ES 3.2 NVIDIA 525.105.17
OpenGL ES profile shading language version string: OpenGL ES GLSL ES 3.20
"""
FAKE_GLXINFO_NVIDIA = glxinfo.GlxInfo(SAMPLE_GLXINFO_OUTPUT)
SAMPLE_GPU_INFORMATION = """\
Model:           NVIDIA GeForce GTX 1660 SUPER
IRQ:             35
GPU UUID:        GPU-12345678-1234-1234-1234-1234567890ab
Video BIOS:      90.16.48.00.aa
Bus Type:        PCIe
DMA Size:        47 bits
DMA Mask:        0x7fffffffffff
Bus Location:    0000:01:00.0
Device Minor:    0
GPU Excluded:    No
"""
SAMPLE_GPU_INFO_DICT = {
    "Model": "NVIDIA GeForce GTX 1660 SUPER",
    "IRQ": "35",
    "GPU UUID": "GPU-12345678-1234-1234-1234-1234567890ab",
    "Video BIOS": "90.16.48.00.aa",
    "Bus Type": "PCIe",
    "DMA Size": "47 bits",
    "DMA Mask": "0x7fffffffffff",
    "Bus Location": "0000:01:00.0",
    "Device Minor": "0",
    "GPU Excluded": "No",
}
SAMPLE_LSPCI_GPU = """\
01:00.0 VGA compatible controller: NVIDIA Corporation TU116 \
[GeForce GTX 1660 SUPER] (rev a1) (prog-if 00 [VGA controller])
        Subsystem: eVga.com. Corp. TU116 [GeForce GTX 1660 SUPER]
        Control: I/O+ Mem+ BusMaster+ SpecCycle- MemWINV- VGASnoop- ParErr- Stepping- SERR- FastB2B- DisINTx+
        Status: Cap+ 66MHz- UDF- FastB2B- ParErr- DEVSEL=fast >TAbort- <TAbort- <MAbort- >SERR- <PERR- INTx-
        Latency: 0
        Interrupt: pin A routed to IRQ 35
        Region 0: Memory at f6000000 (32-bit, non-prefetchable) [size=16M]
        Region 1: Memory at e0000000 (64-bit, prefetchable) [size=256M]
        Region 3: Memory at f0000000 (64-bit, prefetchable) [size=32M]
        Region 5: I/O ports at e000 [size=128]
        Expansion ROM at 000c0000 [virtual] [disabled] [size=128K]
        Capabilities: <access denied>
        Kernel driver in use: nvidia
        Kernel modules: nvidiafb, nouveau, nvidia_drm, nvidia
"""
SAMPLE_PROC_MODULES = """\
nvidia_uvm 1384448 2 - Live 0x0000000000000000 (POE)
nvidia_drm 69632 26 - Live 0x0000000000000000 (POE)
nvidia_modeset 1241088 67 nvidia_drm, Live 0x0000000000000000 (POE)
uvcvideo 114688 0 - Live 0x0000000000000000
videobuf2_vmalloc 20480 1 uvcvideo, Live 0x0000000000000000
videobuf2_memops 20480 1 videobuf2_vmalloc, Live 0x0000000000000000
videobuf2_v4l2 32768 1 uvcvideo, Live 0x0000000000000000
nvidia 56500224 3776 nvidia_uvm,nvidia_modeset, Live 0x0000000000000000 (POE)
videobuf2_common 81920 4 uvcvideo,videobuf2_vmalloc,videobuf2_memops,videobuf2_v4l2, Live 0x0000000000000000
videodev 274432 3 uvcvideo,videobuf2_v4l2,videobuf2_common, Live 0x0000000000000000
mc 65536 5 uvcvideo,videobuf2_v4l2,snd_usb_audio,videobuf2_common,videodev, Live 0x0000000000000000
drm_kms_helper 200704 1 nvidia_drm, Live 0x0000000000000000
drm 581632 30 nvidia_drm,nvidia,drm_kms_helper, Live 0x0000000000000000
i2c_nvidia_gpu 16384 0 - Live 0x0000000000000000
i2c_ccgx_ucsi 16384 1 i2c_nvidia_gpu, Live 0x0000000000000000
video 65536 0 - Live 0x0000000000000000
"""


class TestGetNvidiaDriverInfo(unittest.TestCase):
    def test_success_on_current_machine(self):
        drivers.get_nvidia_driver_info()

    @patch("os.path.exists", return_value=False)
    def test_returns_none_if_file_doesnt_exist(self, mock_path_exists):
        self.assertEqual(drivers.get_nvidia_driver_info(), {})

    @patch("builtins.open")
    @patch("os.path.exists", return_value=True)
    def test_from_file(self, mock_path_exists, mock_open):
        for test_type, version_file, expected in DRIVER_VERSION_FILES:
            with self.subTest(test_type):
                mock_open.return_value = io.StringIO(version_file)

                actual = drivers.get_nvidia_driver_info()

                self.assertEqual(actual, expected)

    @patch(
        "builtins.open",
        side_effect=PermissionError(13, "Permission Denied: '/proc/driver/nvidia/version'"),
    )
    @patch("os.path.exists", return_value=True)
    def test_file_errors(self, mock_path_exists, mock_open):
        with patch.object(drivers, "GlxInfo", return_value=FAKE_GLXINFO_NVIDIA):
            with patch.object(
                subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, stdout="Linux\n"),
                    subprocess.CompletedProcess([], 0, stdout="x86_64\n"),
                ],
            ):
                actual = drivers.get_nvidia_driver_info()

                self.assertEqual(
                    actual,
                    {
                        "vendor": "NVIDIA Corporation",
                        "platform": "Linux",
                        "arch": "x86_64",
                        "version": "525.105.17",
                    },
                )


class TestGetNvidiaGpuIds(unittest.TestCase):
    sample_gpu_list = ["0000:01:00.0"]

    @patch("os.listdir", return_value=sample_gpu_list)
    def test_get_from_proc(self, mock_listdir):
        self.assertEqual(drivers.get_nvidia_gpu_ids(), self.sample_gpu_list)

    @patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lspci", "-D", "-n", "-d", "10de::0300"],
            returncode=0,
            stdout="0000:01:00.0 0300: 10de:21c4 (rev a1)\n",
        ),
    )
    @patch("os.listdir", side_effect=PermissionError())
    def test_get_from_lspci(self, mock_listdir, mock_lspci):
        self.assertEqual(drivers.get_nvidia_gpu_ids(), self.sample_gpu_list)


class TestGetNvidiaGpuInfo(unittest.TestCase):
    sample_gpu_id = "0000:01:00.0"

    @patch("builtins.open", return_value=io.StringIO(SAMPLE_GPU_INFORMATION))
    def test_get_from_proc(self, mock_open):
        result = drivers.get_nvidia_gpu_info(self.sample_gpu_id)

        self.assertEqual(result, SAMPLE_GPU_INFO_DICT)

    @patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout=SAMPLE_LSPCI_GPU))
    @patch("builtins.open", side_effect=PermissionError())
    def test_get_from_lspci_glxinfo(self, mock_open, mock_lspci):
        result = drivers.get_nvidia_gpu_info(self.sample_gpu_id)

        self.assertDictContainsSubset(
            {
                "Model": "NVIDIA GeForce GTX 1660 SUPER",
                "IRQ": "35",
                "Bus Location": self.sample_gpu_id,
                "Subsystem": "eVga.com. Corp. TU116 [GeForce GTX 1660 SUPER]",
                "Interrupt": "pin A routed to IRQ 35",
                "Region 0": "Memory at f6000000 (32-bit, non-prefetchable) [size=16M]",
                "Region 1": "Memory at e0000000 (64-bit, prefetchable) [size=256M]",
                "Region 3": "Memory at f0000000 (64-bit, prefetchable) [size=32M]",
                "Region 5": "I/O ports at e000 [size=128]",
                "Kernel driver in use": "nvidia",
            },
            result,
        )


class TestIsNvidia(unittest.TestCase):
    def test_success_on_current_machine(self):
        self.assertIsInstance(drivers.is_nvidia(), bool)

    @patch("os.path.exists", return_value=False)
    def test_not_nvidia_by_directory(self, mock_exists):
        self.assertFalse(drivers.is_nvidia())

    @patch("builtins.open", return_value=io.StringIO(""))
    @patch("os.path.exists", side_effect=PermissionError())
    def test_not_nvidia_proc_modules(self, mock_exists, mock_open):
        self.assertFalse(drivers.is_nvidia())

    # TODO: Add AMD GLX info and uncomment this test.
    # @patch.object(drivers, "GlxInfo", return_value=FAKE_GLXINFO_AMD)
    # @patch("builtins.open", side_effect=PermissionError())
    # @patch("os.path.exists", side_effect=PermissionError())
    # def test_not_nvidia_glxinfo(self, mock_exists, mock_open, mock_glxinfo):
    #     self.assertFalse(drivers.is_nvidia())

    @patch("os.path.exists", return_value=True)
    def test_is_nvidia_by_directory(self, mock_exists):
        self.assertTrue(drivers.is_nvidia())

    @patch("builtins.open", return_value=io.StringIO(SAMPLE_PROC_MODULES))
    @patch("os.path.exists", side_effect=PermissionError())
    def test_is_nvidia_proc_modules(self, mock_exists, mock_open):
        self.assertTrue(drivers.is_nvidia())

    @patch.object(drivers, "GlxInfo", return_value=FAKE_GLXINFO_NVIDIA)
    @patch("builtins.open", side_effect=PermissionError())
    @patch("os.path.exists", side_effect=PermissionError())
    def test_is_nvidia_glxinfo(self, mock_exists, mock_open, mock_glxinfo):
        self.assertTrue(drivers.is_nvidia())
