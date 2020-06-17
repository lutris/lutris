# i18n

i18n build only works with the meson build system. See github issue #728 for more details.

## Updating a translations

```bash
meson transl-builddir
ninja build -C transl-builddir
ninja lutris-update-po -C transl-builddir
```
Now edit the `$LANG.po` file, and run after that
```bash
ninja lutris-update-po -C transl-builddir
rm -Rf transl-builddir
```
and commit your changes.

## Creating a translation

```bash
meson transl-builddir
ninja build -C transl-builddir
ninja lutris-pot -C transl-builddir
mv po/lutris.pot po/$LANG.po
```
Now edit the `$LANG.po` file, and run after that
```bash
ninja build -C transl-builddir
ninja lutris-update-po -C transl-builddir
rm -Rf transl-builddir
```
and commit your changes.

## Notes

- Only commit changes for the translation file you actually edited.
- Ignore or delete the first four lines (copyright notice) in the `$LANG.po` files.
- The `LINGUAS` and `POTFILES` updated by the `ninja build -C transl-builddir` command. You don't need to edit them manually.
- Languages can't be tested without installing Lutris via meson:
  ```bash
  rm -Rf transl-builddir
  meson transl-builddir --prefix=~/.local
  ninja build -C transl-builddir
  ninja install -C transl-builddir
  env LANGUAGE=$LANG ~/.local/bin/lutris
  ```
