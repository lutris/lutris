# pylint: disable=missing-docstring
# Standard Library
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree

# Lutris Modules
from lutris.util.log import logger


class CabInstaller:

    """Extract and install contents of cab files

    Based on an implementation by tonix64: https://github.com/tonix64/python-installcab
    """

    def __init__(self, prefix, arch=None, wine_path=None):
        self.prefix = prefix
        self.winearch = arch or self.get_wineprefix_arch()
        self.tmpdir = tempfile.mkdtemp()
        self.wine_path = wine_path

        self.register_dlls = False  # Whether to register DLLs, I don't the purpose of that
        self.strip_dlls = False  # When registering, strip the full path

    @staticmethod
    def process_key(key):
        """I have no clue why"""
        return key.strip("\\").replace("HKEY_CLASSES_ROOT", "HKEY_LOCAL_MACHINE\\Software\\Classes")

    @staticmethod
    def get_arch_from_manifest(root):
        registry_keys = root.findall("{urn:schemas-microsoft-com:asm.v3}assemblyIdentity")
        arch = registry_keys[0].attrib["processorArchitecture"]
        arch_map = {"amd64": "win64", "x86": "win32", "wow64": "wow64"}
        return arch_map[arch]

    def get_winebin(self, arch):
        wine_path = self.wine_path or "wine"
        return wine_path if arch in ("win32", "wow64") else wine_path + "64"

    @staticmethod
    def get_arch_from_dll(dll_path):
        if "x86-64" in subprocess.check_output(["file", dll_path]).decode():
            return "win64"
        return "win32"

    def cleanup(self):
        logger.info("Cleaning up %s", self.tmpdir)
        shutil.rmtree(self.tmpdir)

    def check_dll_arch(self, dll_path):
        return self.get_arch_from_dll(dll_path)

    def replace_variables(self, value, arch):
        if "$(" in value:
            value = value.replace("$(runtime.help)", "C:\\windows\\help")
            value = value.replace("$(runtime.inf)", "C:\\windows\\inf")
            value = value.replace("$(runtime.wbem)", "C:\\windows\\wbem")
            value = value.replace("$(runtime.windows)", "C:\\windows")
            value = value.replace("$(runtime.ProgramFiles)", "C:\\windows\\Program Files")
            value = value.replace("$(runtime.programFiles)", "C:\\windows\\Program Files")
            value = value.replace("$(runtime.programFilesX86)", "C:\\windows\\Program Files (x86)")
            value = value.replace("$(runtime.system32)", "C:\\windows\\%s" % self.get_system32_realdir(arch))
            value = value.replace(
                "$(runtime.drivers)",
                "C:\\windows\\%s\\drivers" % self.get_system32_realdir(arch),
            )
        value = value.replace("\\", "\\\\")
        return value

    def process_value(self, reg_value, arch):
        attrs = reg_value.attrib
        name = attrs["name"]
        value = attrs["value"]
        value_type = attrs["valueType"]
        if not name.strip():
            name = "@"
        else:
            name = '"%s"' % name
        name = self.replace_variables(name, arch)
        if value_type == "REG_BINARY":
            value = re.findall("..", value)
            value = "hex:" + ",".join(value)
        elif value_type == "REG_DWORD":
            value = "dword:%s" % value.replace("0x", "")
        elif value_type == "REG_QWORD":
            value = "qword:%s" % value.replace("0x", "")
        elif value_type == "REG_NONE":
            value = None
        elif value_type == "REG_EXPAND_SZ":
            # not sure if we should replace this ones at this point:
            # caps can vary in the pattern
            value = value.replace("%SystemRoot%", "C:\\windows")
            value = value.replace("%ProgramFiles%", "C:\\windows\\Program Files")
            value = value.replace("%WinDir%", "C:\\windows")
            value = value.replace("%ResourceDir%", "C:\\windows")
            value = value.replace("%Public%", "C:\\users\\Public")
            value = value.replace("%LocalAppData%", "C:\\windows\\Public\\Local Settings\\Application Data")
            value = value.replace("%AllUsersProfile%", "C:\\windows")
            value = value.replace("%UserProfile%", "C:\\windows")
            value = value.replace("%ProgramData%", "C:\\ProgramData")
            value = '"%s"' % value
        elif value_type == "REG_SZ":
            value = '"%s"' % value
        else:
            logger.warning("warning unkown type: %s", value_type)
            value = '"%s"' % value
        if value:
            value = self.replace_variables(value, arch)
            if self.strip_dlls:
                if ".dll" in value:
                    value = value.lower().replace("c:\\\\windows\\\\system32\\\\", "")
                    value = value.lower().replace("c:\\\\windows\\\\syswow64\\\\", "")
        return name, value

    def get_registry_from_manifest(self, file_name):
        out = ""
        root = xml.etree.ElementTree.parse(file_name).getroot()
        arch = self.get_arch_from_manifest(root)
        registry_keys = root.findall("{urn:schemas-microsoft-com:asm.v3}registryKeys")
        if registry_keys:
            for registry_key in registry_keys[0].getchildren():
                key = self.process_key(registry_key.attrib["keyName"])
                out += "[%s]\n" % key
                for reg_value in registry_key.findall("{urn:schemas-microsoft-com:asm.v3}registryValue"):
                    name, value = self.process_value(reg_value, arch)
                    if value is not None:
                        out += "%s=%s\n" % (name, value)
                out += "\n"
        return (out, arch)

    def get_wineprefix_arch(self):
        with open(os.path.join(self.prefix, "system.reg")) as reg_file:
            for line in reg_file.readlines():
                if line.startswith("#arch=win32"):
                    return "win32"
                if line.startswith("#arch=win64"):
                    return "win64"
        return "win64"

    def get_system32_realdir(self, arch):
        dest_map = {
            ("win64", "win32"): "Syswow64",
            ("win64", "win64"): "System32",
            ("win64", "wow64"): "System32",
            ("win32", "win32"): "System32",
        }
        return dest_map[(self.winearch, arch)]

    def get_dll_destdir(self, dll_path):
        if self.get_arch_from_dll(dll_path) == "win32" and self.winearch == "win64":
            return os.path.join(self.prefix, "drive_c/windows/syswow64")
        return os.path.join(self.prefix, "drive_c/windows/system32")

    def install_dll(self, dll_path):
        dest_dir = self.get_dll_destdir(dll_path)
        logger.debug("Copying %s to %s", dll_path, dest_dir)
        shutil.copy(dll_path, dest_dir)

        dest_dll_path = os.path.join(dest_dir, os.path.basename(dll_path))
        if not self.register_dlls:
            return
        arch = self.get_arch_from_dll(dest_dll_path)
        subprocess.call([self.get_winebin(arch), "regsvr32", os.path.basename(dest_dll_path)])

    def get_registry_files(self, output_files):
        reg_files = []
        for file_path in output_files:
            if file_path.endswith(".manifest"):
                out = "Windows Registry Editor Version 5.00\n\n"
                outdata, arch = self.get_registry_from_manifest(file_path)
                if outdata:
                    out += outdata
                    with open(os.path.join(self.tmpdir, file_path + ".reg"), "w") as reg_file:
                        reg_file.write(out)
                    reg_files.append((file_path + ".reg", arch))
            if file_path.endswith(".dll"):
                self.install_dll(file_path)
        return reg_files

    def apply_to_registry(self, file_path, arch):
        logger.info("Applying %s to registry", file_path)
        subprocess.call([self.get_winebin(arch), "regedit", os.path.join(self.tmpdir, file_path)])

    def extract_from_cab(self, cabfile, component):
        """Extracts files matching a `component` name from a `cabfile`

        Params:
            cabfile (str): Path to a cabfile to extract from
            component (str): component to extract from the cab file

        Returns:
            list: Files extracted from the cab file
        """
        subprocess.check_output(["cabextract", "-F", "*%s*" % component, "-d", self.tmpdir, cabfile])
        return [os.path.join(r, file) for r, d, f in os.walk(self.tmpdir) for file in f]

    def install(self, cabfile, component):
        """Install `component` from `cabfile`"""
        logger.info("Installing %s from %s", component, cabfile)

        for file_path, arch in self.get_registry_files(self.extract_from_cab(cabfile, component)):
            self.apply_to_registry(file_path, arch)

        self.cleanup()
