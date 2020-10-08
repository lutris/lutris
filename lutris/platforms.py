"""Generic platform functions."""
# Standard Library
from collections import defaultdict

# Lutris Modules
from lutris import runners

# gets populated by _init_platforms()
__all__ = defaultdict(list)


def _init_platforms():
    for runner_name in runners.__all__:
        runner = runners.import_runner(runner_name)()
        for platform in runner.platforms:
            __all__[platform].append(runner_name)


_init_platforms()


LONG_PLATFORM_OVERRIDES = {
    "Odyssey": "Magnavox Odyssey",
    "Intellivision": "Mattel Intellivision",
    "PC-8000 / PC-8800 series": "NEC PC-88",
    "Vectrex": "GCE Vectrex",
    "VIC20": "Commodore VIC20",
    "CPC": "Amstrad CPC",
    "MSX": "Microsoft MSX",
    "Nintendo Entertainment System": "Nintendo NES",
    "Master System": "Sega Master System",
    "PC-98": "NEC PC-98",
    "ZX81": "Sinclair ZX81",
    "ZX Spectrum (various)": "Sinclair ZX Spectrum",
    "Game Boy/Game Boy Color": "Nintendo Game Boy/Game Boy Color",
    "Game Gear": "Sega Game Gear",
    "Genesis": "Sega Genesis",
    "Lynx": "Atari Lynx",
    "Neo Geo": "SNK Neo Geo",
    "32X": "Sega 32X",
    "X68000": "Sharp X68000",
    "Super Nintendo Entertainment System": "Nintendo SNES",
    "Jaguar": "Atari Jaguar",
    "PC-FX": "NEC PC-FX",
    "PlayStation": "Sony PlayStation",
    "Saturn": "Sega Saturn",
    "Virtual Boy": "Nintendo Virtual Boy",
    "WonderSwan/Color": "Bandai WonderSwan/WonderSwan Color",
    "Dreamcast": "Sega Dreamcast",
    "Game Boy Advance": "Nintendo Game Boy Advance",
    "Gamecube": "Nintendo Gamecube",
    "Neo Geo Pcket (Color)": "SNK Neo Geo Pocket/Neo Geo Pocket Color",
    "PlayStation 2": "Sony PlayStation 2",
    "Xbox": "Microsoft Xbox",
    "DS": "Nintendo DS",
    "PlayStation 3": "Sony PlayStation 3",
    "PlayStation Portable": "Sony PlayStation Portable",
    "Wii": "Nintendo Wii",
    "Xbox 360": "Microsoft Xbox 360",
    "3DS": "Nintendo 3DS",
    "PlayStation Vita": "Sony PlayStation Vita",
    "Wii U": "Nintendo Wii U",
    "Switch": "Nintendo Switch",
    "PlayStation 4": "Sony PlayStation 4",
    "Stadia": "Google Stadia",
    "Xbox One": "Microsoft Xbox One"
}
