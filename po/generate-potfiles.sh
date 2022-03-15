#!/bin/sh

cd "$(dirname "$(realpath "$0")")/.."

echo "# generated on $(date -u -Iseconds)" > po/POTFILES

echo "" >> po/POTFILES
echo "share/applications/net.lutris.Lutris.desktop" >> po/POTFILES
echo "share/metainfo/net.lutris.Lutris.metainfo.xml" >> po/POTFILES

echo "" >> ./po/POTFILES
find share/lutris/ui -name '*.ui' | sort >> po/POTFILES

echo "" >> ./po/POTFILES
find lutris -name '*.py' | sort >> po/POTFILES
