# i18n

Please read the notes below before opening a PR.

Note: All the commands below need to be run in the project root directory, not in the `po` directory. Otherwise you may get `Not the project root` error in meson.

## Update POTFILES

Before you start translating, you may want to update `POTFILES`, which contains a list of all source files that need to be translated.

If someone deletes or renames some file, it has to be updated, otherwise "No such file or directory" will throw.

Run the following command to update:

```
./po/generate-potfiles.sh
```

## Updating a translation

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
