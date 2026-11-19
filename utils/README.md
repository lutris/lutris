# Utils

Helper scripts and build tooling. Nothing here is imported by the Lutris
application; these are developer- and build-facing helpers.

## Standalone scripts

| Script | Purpose | Used by |
|--------|---------|---------|
| `meson_post_install.py` | Meson install hook: refreshes the icon cache and desktop database. | `meson.build` (`meson.add_install_script`) |
| `bios_format.py` | One-off utility to reformat BIOS/firmware definition data. | Manual use |
| `cleanup_prefix.py` | Removes known runner directories from a Wine prefix. | Manual use |
| `release-smoke-test.sh` | End-to-end release check on a throwaway sandbox over a private D-Bus session: first start, upgrade of an old profile, game launch, export/import. | `make smoke`, `docs/release-guidelines.rst` |
