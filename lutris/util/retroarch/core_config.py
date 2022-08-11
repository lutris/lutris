RECOMMENDED_CORES = {
    "mesen": {
        "platforms": ["nes"],
        "extensions": [
            ".nes",
            ".fds",
            ".unf",
            ".unif",
        ]
    },
    "gambatte": {
        "platforms": ["gameboy", "gameboy_color"],
        "bios": [
            {
                "filename": "gb_bios.bin",
                "description": "Game Boy BIOS - Optional",
                "md5sum": "32fbbd84168d3482956eb3c5051637f5",
                "required": False
            },
            {
                "filename": "gbc_bios.bin",
                "description": "Game Boy Color BIOS - Optional",
                "md5sum": "dbfce9db9deaa2567f6a84fde55f9680",
                "required": False
            }
        ],
        "extensions": [
            ".gb",
            ".gbc",
            ".dmg",
        ]
    },
    "snes9x": {
        "platforms": ["snes"],
        "extensions": [
            ".smc",
            ".sfc",
            ".swc",
            ".fig",
            ".bs",
            ".st",
        ]
    },
    "picodrive": {
        "platforms": [
            "master_system",
            "game_gear",
            "genesis",
            "mega_cd",
            "32x"
        ],
        "extensions": [
            ".mdx",
            ".md",
            ".smd",
            ".gen",
            ".bin",
            ".cue",
            ".iso",
            ".sms",
            ".gg",
            ".sg",
            ".68k",
            ".chd",
        ]
    },
    "opera": {
        "platforms": ["3do"],
        "extensions": [
            ".iso",
            ".bin",
            ".chd",
            ".cue",
        ],
        "bios": [
            {
                "filename": "panafz1.bin",
                "description": "Panasonic FZ-1",
                "md5sum": "f47264dd47fe30f73ab3c010015c155b"
            },
            {
                "filename": "panafz10.bin",
                "description": "Panasonic FZ-10",
                "md5sum": "51f2f43ae2f3508a14d9f56597e2d3ce"
            },
            {
                "filename": "panafz10-norsa.bin",
                "description": "Panasonic FZ-10 [RSA Patch]",
                "md5sum": "1477bda80dc33731a65468c1f5bcbee9"
            },
            {
                "filename": "panafz10e-anvil.bin",
                "description": "Panasonic FZ-10-E [Anvil]",
                "md5sum": "a48e6746bd7edec0f40cff078f0bb19f"
            },
            {
                "filename": "panafz10e-anvil-norsa.bin",
                "description": "Panasonic FZ-10-E [Anvil RSA Patch]",
                "md5sum": "cf11bbb5a16d7af9875cca9de9a15e09"
            },
            {
                "filename": "panafz1j.bin",
                "description": "Panasonic FZ-1J",
                "md5sum": "a496cfdded3da562759be3561317b605"
            },
            {
                "filename": "panafz1j-norsa.bin",
                "description": "Panasonic FZ-1J [RSA Patch]",
                "md5sum": "f6c71de7470d16abe4f71b1444883dc8"
            },
            {
                "filename": "goldstar.bin",
                "description": "Goldstar GDO-101M",
                "md5sum": "8639fd5e549bd6238cfee79e3e749114"
            },
            {
                "filename": "sanyotry.bin",
                "description": "Sanyo IMP-21J TRY",
                "md5sum": "35fa1a1ebaaeea286dc5cd15487c13ea"
            },
            {
                "filename": "3do_arcade_saot.bin",
                "description": "Shootout At Old Tucson",
                "md5sum": "8970fc987ab89a7f64da9f8a8c4333ff"
            }
        ],
    },
    "mupen64plus_next": {
        "platforms": ["n64"],
        "extensions": [
            ".z64",
            ".n64",
            ".v64"
        ]
    }
}
