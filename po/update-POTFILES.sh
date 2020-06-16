#!/bin/sh
cd "$(dirname "$(realpath "$0")")/.."
find . -name '*.ui' > ./po/POTFILES
find . -name '*.py' >> ./po/POTFILES
