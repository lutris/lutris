#!/usr/bin/env python
"""Surprise !"""

STANDARD_CODES = {
    "[a]":   "Alternate",
    "[p]":   "Pirate",
    "[t]":   "Trained",
    "[T-]":  "OldTranslation",
    "[T+]":  "NewerTranslation",
    "(-)":   "Unknown Year",
    "[!]":   "Verified Good Dump",
    "(\d+)": "(# of Languages)",
    "(??k)": "ROM Size",
    "(Unl)": "Unlicensed",
    "[b]": "Bad Dump",
    "[f]": "Fixed",
    "[h]": "Hack",
    "[o]": "Overdump",
    "(M#)": "Multilanguage",
    "(###)": "Checksum",
    "ZZZ_": "Unclassified"
}
