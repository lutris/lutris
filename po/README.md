# i18n

Please read the notes below before opening a PR.

## Updating a translations

```bash
meson builddir
ninja lutris-update-po -C builddir
```
Now update the `$LANG.po` file, and run after that
```bash
ninja lutris-update-po -C builddir
rm -Rf builddir
```
and commit your changes.

## Creating a translation

```bash
meson builddir
ninja lutris-pot -C builddir
mv po/lutris.pot po/$LANG.po
```
Now edit the `$LANG.po` file, add `$LANG` to the `LINGUAS` file, and run after that
```bash
ninja lutris-update-po -C builddir
rm -Rf builddir
```
and commit your changes.

## Notes

- Only commit changes for the translation file you actually edited.
- Delete the first five lines (copyright notice) in the `$LANG.po` files.
- Keep the `LINGUAS` file sorted alphabetically.
- The files to translate might change, run `./po/generate-potfiles.sh` to check if there are changes in the files list. If that is the case, commit the change.
- Languages can't be tested without installing Lutris via meson:
  ```bash
  rm -Rf builddir
  meson builddir --prefix=~/.local
  ninja install -C builddir
  env LANGUAGE=$LANG ~/.local/bin/lutris
  ```
