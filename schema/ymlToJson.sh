#!/usr/bin/env bash
SELF_DIR="$(dirname "$0")"
if [[ -z "$1" ]]; then
  echo "ERROR: No YAML file passed in!"
  exit 1
fi
base="$(basename "$1")"
target="${base%.*}.json"
echo "INFO: $1 > $target"
curl -d "$(cat "$SELF_DIR/$1")" \
    -H "Content-Type: text/plain" \
    -H 'Accept: application/json' \
    -o "$SELF_DIR/$target" \
    https://www.anyjson.in/api/v2/data/yamltojson &> /dev/null
