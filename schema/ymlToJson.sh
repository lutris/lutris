#!/usr/bin/env bash
SELF_DIR="$(dirname "$0")"

curl -d "$(cat "$SELF_DIR/installer.schema.yml")" \
    -H "Content-Type: text/plain" \
    -H 'Accept: application/json' \
    -o "$SELF_DIR/installer.schema.json" \
    https://www.anyjson.in/api/v2/data/yamltojson
