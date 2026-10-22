#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROGRAM=${1:-"$ROOT/examples/native.सूत्र"}
GENERATED="$HERE/generated"
TEMP=$(mktemp -d)
trap 'rm -rf "$TEMP"' EXIT HUP INT TERM
"$ROOT/bin/peacock" native "$PROGRAM" --library --keep-c "$GENERATED" -o "$TEMP/libpeacock-host.so"
printf 'iOS C sources prepared in %s\n' "$GENERATED"
printf '%s\n' 'On macOS with Xcode, run shells/ios/build-simulator.sh'
