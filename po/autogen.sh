#!/bin/sh
cd "$(dirname "$(realpath "$0")")/.."

# POTFILES
find . -name '*.ui' | sort > ./po/POTFILES
find . -name '*.py' | sort >> ./po/POTFILES

# LINGUAS
cd ./po
find . -name '*.po' | sed 's#^\./##' | sed 's#\.po$##' | sort > ./LINGUAS
