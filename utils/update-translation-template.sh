#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
desktop=packaging/desktop/share
template=lutris/locale/lutris.pot

find lutris -name '*.py' | LC_ALL=C sort | xgettext --from-code=UTF-8 --keyword=_ --package-name=Lutris \
    --files-from=- --output="$template" \
    "$desktop/applications/net.lutris.Lutris.desktop" "$desktop/metainfo/net.lutris.Lutris.metainfo.xml"
find lutris/qt/qml -name '*.qml' | LC_ALL=C sort | xgettext --from-code=UTF-8 --language=JavaScript --keyword=qsTr \
    --join-existing --files-from=- --output="$template"
