#!/bin/sh
set -eu
# Requires macOS, Xcode and an iOS Simulator SDK. No device signing is done.
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
GENERATED=${1:-"$HERE/generated"}
OUTPUT=${2:-"$HERE/build/Peacock.app"}
[ -f "$GENERATED/program.c" ] || { echo 'run prepare.sh first' >&2; exit 2; }
SDK=$(xcrun --sdk iphonesimulator --show-sdk-path)
CLANG=$(xcrun --find clang)
SWIFTC=$(xcrun --find swiftc)
case $(uname -m) in arm64) ARCH=arm64 ;; x86_64) ARCH=x86_64 ;; *) echo 'unsupported simulator architecture' >&2; exit 2 ;; esac
TARGET="$ARCH-apple-ios17.0-simulator"
OBJECTS="$OUTPUT.objects"
rm -rf "$OBJECTS"
mkdir -p "$OBJECTS" "$OUTPUT"
CFLAGS="-target $TARGET -isysroot $SDK -mios-simulator-version-min=17.0 -O2 -Wall -Wextra -Werror"
$CLANG $CFLAGS -fPIC -I"$GENERATED" -c "$GENERATED/program.c" -o "$OBJECTS/program.o"
$CLANG $CFLAGS -fPIC -I"$GENERATED" -c "$GENERATED/runtime.c" -o "$OBJECTS/runtime.o"
$CLANG $CFLAGS -fPIC -fobjc-arc -fmodules -I"$GENERATED" -I"$HERE" -c "$HERE/PeacockRunner.m" -o "$OBJECTS/runner.o"
$SWIFTC -target "$TARGET" -sdk "$SDK" -import-objc-header "$HERE/PeacockBridge.h" \
    "$HERE/PeacockApp.swift" "$OBJECTS/program.o" "$OBJECTS/runtime.o" "$OBJECTS/runner.o" \
    -o "$OUTPUT/Peacock"
cp "$HERE/Info.plist" "$OUTPUT/Info.plist"
printf '%s\n' "$OUTPUT"
