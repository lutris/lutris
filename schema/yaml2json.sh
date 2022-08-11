#!/usr/bin/env bash

yaml2json() {
    if [[ -z "$1" ]]; then
        echo "ERROR: No YAML file passed in!"
        exit 1
    fi
    base="$(basename "$1")"
    target="${base%.*}.json"
    echo "INFO: $1 > $target"
    curl -d "$(cat "$1")" \
        -H "Content-Type: text/plain" \
        -H 'Accept: application/json' \
        -o "$target" \
        https://www.anyjson.in/api/v2/data/yamltojson &>/dev/null
}

if [[ -z "$*" ]]; then
    echo "USAGE: $0 path/to/file1.yml path/to/file2.yaml"
else
    for var in "$@"; do
        yaml2json "$var"
    done
fi
