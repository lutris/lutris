import json


bios_list = """
gb_bios.bin 	Game Boy BIOS - Optional 	32fbbd84168d3482956eb3c5051637f5
gbc_bios.bin 	Game Boy Color BIOS - Optional 	dbfce9db9deaa2567f6a84fde55f9680
"""


bioses = []
for bios_line in bios_list.split("\n"):
    if not bios_line:
        continue
    filename, _rest = bios_line.split(maxsplit=1)
    sysname, checksum = _rest.rsplit(maxsplit=1)
    bioses.append({
        "filename": filename,
        "description": sysname,
        "md5sum": checksum,
    })

print(json.dumps(bioses, indent=4))
