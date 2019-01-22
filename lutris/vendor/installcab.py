#! /usr/bin/env python
import os
import sys
import subprocess
import tempfile
import shutil

import xml.etree.ElementTree
import re

tmpdir = None

#######################################
# Utils

def cleanup():
    if not tmpdir:
        return
    if options['nocleanup']:
        print("Not cleaning up. Find the files at %s" % tmpdir)
    else:
        shutil.rmtree(tmpdir)

def bad_exit(text):
    print(text)
    cleanup()
    sys.exit(1)

def print_debug(text):
    if options['debug']:
        print(text)

#######################################
# Architecture helpers

arch_map = {
    "amd64": "win64",
    "x86": "win32",
    "wow64": "wow64"
}

dest_map = {
    "win64:win32": "Syswow64",
    "win64:win64": "System32",
    "win64:wow64": "System32",
    "win32:win32": "System32"
}

def check_wineprefix_arch(prefix_path):
    if not os.path.exists(prefix_path):
        bad_exit("Wineprefix path does not exist! (%s)" % prefix_path)
    system_reg_file = os.path.join(prefix_path, 'system.reg')
    with open(system_reg_file) as f:
        for line in f.readlines():
            if line.startswith("#arch=win32"):
                return 'win32'
            elif line.startswith("#arch=win64"):
                return 'win64'
        bad_exit("Could not determine wineprefix arch!")

def get_system32_realdir(arch):
    return dest_map[winearch+':'+arch]

def get_dll_destdir(dll_path):
    arch = check_dll_arch(dll_path)
    if arch == 'win32' and winearch == 'win64':
        dest_dir = syswow64_path
    elif arch == 'win64' and winearch == 'win32':
        bad_exit("Invalid win64 assembly for win32 wineprefix!")
    else:
        dest_dir = system32_path
    return dest_dir

def get_winebin(arch):
    if (arch == 'win64' or arch == 'wow64') and winearch == 'win32':
        bad_exit("Invalid win64 assembly for win32 wineprefix!")
    elif arch == 'win32' or arch == 'wow64':
        winebin = 'wine'
    else:
        winebin = 'wine64'
    return winebin

def check_dll_arch(dll_path):
    out = subprocess.check_output(['file', dll_path])
    if 'x86-64' in out:
        return 'win64'
    else:
        return 'win32'

#######################################
# Manifest processing

def replace_variables(value, arch):
    if "$(" in value:
        value = value.replace("$(runtime.help)", "C:\\windows\\help")
        value = value.replace("$(runtime.inf)", "C:\\windows\\inf")
        value = value.replace("$(runtime.wbem)", "C:\\windows\\wbem")
        value = value.replace("$(runtime.windows)", "C:\\windows")
        value = value.replace("$(runtime.ProgramFiles)", "C:\\windows\\Program Files")
        value = value.replace("$(runtime.programFiles)", "C:\\windows\\Program Files")
        value = value.replace("$(runtime.programFilesX86)", "C:\\windows\\Program Files (x86)")
        value = value.replace("$(runtime.system32)", "C:\\windows\\%s" % get_system32_realdir(arch))
        value = value.replace("$(runtime.drivers)", "C:\\windows\\%s\\drivers" % get_system32_realdir(arch))
    value = value.replace("\\", "\\\\")
    return value

def process_value(rv, arch):
    attrs = rv.attrib
    name = attrs["name"]
    value = attrs["value"]
    value_type = attrs["valueType"]
    if not name.strip():
        name = "@"
    else:
        name = "\"%s\"" % name
    name = replace_variables(name, arch)
    if value_type == 'REG_BINARY':
        value = re.findall('..',value)
        value = 'hex:'+",".join(value)
    elif value_type == 'REG_DWORD':
        value = "dword:%s" % value.replace("0x", "")
    elif value_type == 'REG_QWORD':
        value = "qword:%s" % value.replace("0x", "")
    elif value_type == 'REG_NONE':
        value = None
    elif value_type == 'REG_EXPAND_SZ':
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
        value = "\"%s\"" % value
    elif value_type == 'REG_SZ':
        value = "\"%s\"" % value
    else:
        print("warning unkown type: %s" % value_type)
        value = "\"%s\"" % value
    if value:
        value = replace_variables(value, arch)
        if options["stripdllpath"]:
            if '.dll' in value:
                value = value.lower().replace("c:\\\\windows\\\\system32\\\\", "")
                value = value.lower().replace("c:\\\\windows\\\\syswow64\\\\", "")
    return name, value

def process_key(key):
    key = key.strip("\\")
    key = key.replace("HKEY_CLASSES_ROOT", "HKEY_LOCAL_MACHINE\\Software\\Classes")
    return key

def parse_manifest_arch(elmt):
    registry_keys = elmt.findall("{urn:schemas-microsoft-com:asm.v3}assemblyIdentity")
    if not len(registry_keys):
        bad_exit("Can't find processor architecture")
    arch = registry_keys[0].attrib["processorArchitecture"]
    if not arch in arch_map:
        bad_exit("Unknown processor architecture %s" % arch)
    arch = arch_map[arch]
    if (arch == 'win64' or arch == 'wow64') and winearch == 'win32':
        bad_exit("Invalid 64 bit assembly for 32 bit system!")
    return arch

def process_manifest(file_name):
    out = ""
    elmt = xml.etree.ElementTree.parse(file_name).getroot()
    arch = parse_manifest_arch(elmt)
    registry_keys = elmt.findall("{urn:schemas-microsoft-com:asm.v3}registryKeys")
    if len(registry_keys):
        for registry_key in registry_keys[0].getchildren():
            key = process_key(registry_key.attrib["keyName"])
            out += "[%s]\n" % key
            for rv in registry_key.findall("{urn:schemas-microsoft-com:asm.v3}registryValue"):
                name, value = process_value(rv, arch)
                if not value is None:
                    out += "%s=%s\n"%(name,value)
            out += "\n"
    return (out, arch)


#######################################
# Installer Processing

def extract_from_installer(orig_file, dest_dir, component):
    filter_str = "*%s*" % component
    print("%s" % component.strip("_"))
    cmd = ["cabextract", "-F", filter_str, "-d", dest_dir, orig_file]
    subprocess.check_output(cmd)
    output_files = [os.path.join(r,file) for r,d,f in os.walk(dest_dir) for file in f]
    return output_files

def load_manifest(file_path):
    file_name = os.path.basename(file_path)
    reg_data, arch = process_manifest(file_path)
    print("- %s (%s)" % (file_name, arch))
    return reg_data, arch

def register_dll(dll_path):
    if not options["register"]:
        return
    arch = check_dll_arch(dll_path)
    winebin = get_winebin(arch)
    cmd = ["regsvr32", os.path.basename(dll_path)]
    subprocess.call(cmd)

def install_dll(dll_path):
    if options["nodll"]:
        return
    dest_dir = get_dll_destdir(dll_path)
    file_name = os.path.basename(dll_path)
    print("- %s -> %s" % (file_name, dest_dir))
    shutil.copy(dll_path, dest_dir)
    register_dll(os.path.join(dest_dir, file_name))

def install_regfile(path, reg_file, arch):
    if options["noreg"]:
        return
    winebin = get_winebin(arch)
    print_debug("  install reg %s with %s" % (reg_file, winebin))
    cmd = [winebin, "regedit", os.path.join(path, reg_file)]
    subprocess.call(cmd)

def process_files(output_files):
    reg_files = []
    for file_path in output_files:
        if file_path.endswith(".manifest"):
            out = "Windows Registry Editor Version 5.00\n\n"
            outdata, arch = load_manifest(file_path)
            if outdata:
                out += outdata
                print_debug("  %s assembly" % arch)
                with open(os.path.join(tmpdir, file_path+".reg"), "w") as f:
                    f.write(out)
                reg_files.append((file_path, arch))

    for file_path in output_files:
        if file_path.endswith(".dll"):
            install_dll(file_path)

    for file_path, arch in reg_files:
        install_regfile(tmpdir, file_path+".reg", arch)


#######################################
# Command line options

options = {'register': False, 'nocleanup': False, 'nodll': False, 'noreg': False, 'stripdllpath': False, 'debug': False}

def parse_command_line_opts(options):
    app_argv = list(sys.argv)
    for opt_key in options.keys():
        opt_command = "--%s" % opt_key
        if opt_command in app_argv:
            options[opt_key] = True
            app_argv.remove(opt_command)
    return app_argv


#######################################
# Main

if __name__ == '__main__':
    app_argv = parse_command_line_opts(options)
    # sanity checks
    if len(app_argv) < 3:
        print("usage:")
        print("  installcab.py [options] cabfile component [wineprefix_path]")
        print("")
        print("example:")
        print("  installcab.py ~/.cache/winetricks/win7sp1/windows6.1-KB976932-X86.exe wmvdecod")
        print("")
        print("options:")
        print("  --nocleanup: do not perform cleanup")
        print("  --noreg: do not import registry entries")
        print("  --nodll: do not install dlls into system dir")
        print("  --register: register dlls with regsrv32")
        print("  --stripdllpath: strip full path for dlls in registry so wine can find them anywhere")
        sys.exit(0)

    if len(app_argv) < 4 and not "WINEPREFIX" in os.environ:
        bad_exit("You need to set WINEPREFIX for this to work!")

    # setup
    if len(app_argv) < 4:
        wineprefix = os.environ["WINEPREFIX"]
    else:
        wineprefix = app_argv[3]

    winearch = check_wineprefix_arch(wineprefix)

    system32_path = os.path.join(wineprefix, 'drive_c', 'windows', 'system32')
    syswow64_path = os.path.join(wineprefix, 'drive_c', 'windows', 'syswow64')

    tmpdir = tempfile.mkdtemp()
    cabfile = app_argv[1]
    component = app_argv[2]

    # processing
    output_files = extract_from_installer(cabfile, tmpdir, component)
    process_files(output_files)

    # clean up
    cleanup()

