# Utils

Helper scripts and build tooling. Nothing here is imported by the Lutris
application; these are developer- and build-facing helpers.

## Standalone scripts

| Script | Purpose | Used by |
|--------|---------|---------|
| `check_annotations.py` | Flags annotation syntax that crashes on Python < 3.14 (unquoted conditional imports, string literals in `|` unions). | `.github/workflows/static.yml`, `.hooks/pre-commit`, `make annotation-compat` |
| `meson_post_install.py` | Meson install hook: refreshes the icon cache and desktop database. | `meson.build` (`meson.add_install_script`) |
| `bios_format.py` | One-off utility to reformat BIOS/firmware definition data. | Manual use |
| `cleanup_prefix.py` | Removes known runner directories from a Wine prefix. | Manual use |

## AppImage build

The `appimage/` directory builds the standalone AppImage:

| File | Purpose |
|------|---------|
| `build.sh` | Host-side wrapper: builds/reuses the Docker image and runs the in-container build. Invoked by `make appimage` and the AppImage workflow. |
| `build-in-container.sh` | Assembles the AppDir and packs the AppImage (runs inside the container). |
| `Dockerfile` | Ubuntu 24.04 build image with the required native/Python dependencies. |
| `AppRun` | Custom AppImage launcher (sets up the bundled Python + GTK environment). |
| `linuxdeploy-plugin-gtk.sh` / `.LICENSE` | Vendored `linuxdeploy-plugin-gtk` (upstream is dormant) so builds stay reproducible. |