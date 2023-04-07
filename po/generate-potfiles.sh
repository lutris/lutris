#!/bin/sh
# SPDX-FileCopyrightText: 2020-2021 Stephan Lachnit <stephanlachnit@debian.org>
# 
# SPDX-License-Identifier: GPL-3.0-or-later

cd "$(dirname "$(realpath "$0")")/.."

echo "# generated on $(date -u -Iseconds)" > po/POTFILES

echo "" >> po/POTFILES
echo "share/applications/net.lutris.Lutris.desktop" >> po/POTFILES
echo "share/metainfo/net.lutris.Lutris.metainfo.xml" >> po/POTFILES

echo "" >> ./po/POTFILES
find share/lutris/ui -name '*.ui' | sort >> po/POTFILES

echo "" >> ./po/POTFILES
find lutris -name '*.py' | sort >> po/POTFILES
