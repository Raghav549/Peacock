#!/bin/sh
set -eu

# Usage: build.sh [generated-C-directory] [output-directory]
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
GENERATED=${1:-"$ROOT/generated"}
OUTPUT=${2:-"$ROOT/build"}
CC=${CC:-cc}

if [ ! -f "$GENERATED/program.c" ] || [ ! -f "$GENERATED/runtime.c" ]; then
    echo "missing generated C; run: peacock native PROGRAM.सूत्र --library --keep-c '$GENERATED' -o /tmp/peacock-host.so" >&2
    exit 2
fi
mkdir -p "$OUTPUT"
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared \
    -I"$GENERATED" "$GENERATED/program.c" "$GENERATED/runtime.c" -lm \
    -o "$OUTPUT/libpeacock_program.so"
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -I"$GENERATED" \
    "$ROOT/main.c" -L"$OUTPUT" -lpeacock_program -lm \
    -Wl,-rpath,'$ORIGIN' -o "$OUTPUT/peacock-desktop"
printf '%s\n' "$OUTPUT/peacock-desktop"
