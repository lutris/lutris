# Utils

Helper scripts and build tooling. Nothing here is imported by the Lutris
application; these are developer- and build-facing helpers.

## Standalone scripts

| Script | Purpose | Used by |
|--------|---------|---------|
| `bios_format.py` | One-off utility to reformat BIOS/firmware definition data. | Manual use |
| `cleanup_prefix.py` | Removes known runner directories from a Wine prefix. | Manual use |
| `release-smoke-test.sh` | End-to-end release checks in a throwaway profile over a private D-Bus session. | `docs/release-guidelines.rst` |
| `update-translation-template.sh` | Extracts Python, QML and desktop messages into a gettext template. | `lutris/locale/README.md` |
