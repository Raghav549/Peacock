# Platform hosts and native shells

PEACOCK separates the language runtime from presentation and packaging. The
following statuses distinguish executed evidence from source-only platform
support. **No Android/iOS/OpenCL hardware success is claimed from this Linux
headless development environment.**

## Host backends

| Backend | Purpose | Verification |
|---|---|---|
| `HeadlessBackend` | retain/write `Canvas` frames | existing tests |
| `WebBackend` | PNGs, `latest.png`, manifest and static HTML | real `.सूत्र` presentation tests |
| `ServerBackend` | fixed frame/viewer/health HTTP routes | real HTTP tests |
| `UIWebBackend` | interactive retained UI, `/event` and `/fragment` | real HTTP click unblocks the VM and republishes Sanskrit text |
| `NativeWindowBackend` | X11 window, retained-tree drawing, pointer/key/close events | event-model/headless tests pass; actual display test is opt-in and was not run here |
| C desktop shell | `peacock_run` shared library plus a small native launcher | **executed:** x86-64 PIE; output byte-identical to VM |
| Android Activity/JNI shell | native widgets and generated C runtime | source/generated-C checks only; SDK/NDK/APK/emulator unavailable |
| iOS SwiftUI/Objective-C shell | native app and generated C runtime | source only; Xcode/Apple SDK unavailable |
| WASM | browser runtime/ABI | not implemented |

`WebBackend` for frames is distinct from `UIWebBackend` for retained UI events,
and both are distinct from the static site exporter in `website/site.सूत्र`.

## Interactive UI and native X11 windows

```bash
# Browser host; prints the URL on first दृश्य.प्रदर्शय
./bin/peacock run examples/ui_events.सूत्र --grant दृश्य --ui-serve 8080

# Native X11 host; requires an X11 client library and working DISPLAY
./bin/peacock run examples/ui_events.सूत्र --grant दृश्य --window
```

The browser and X11 hosts deliver events to the same bounded `UIBuilder` queue.
Native close uses the bindable `पिदध्मि` event and wakes a waiting program. X11
core ISO-10646 fonts do not provide PEACOCK with a complete HarfBuzz/Pango-style
complex-script shaping or native accessibility API. With no `DISPLAY`, window
creation fails explicitly (`PE5003` through the host boundary).

An actual display smoke test can be requested on a suitable workstation:

```bash
PEACOCK_TEST_X11=1 DISPLAY="$DISPLAY" \
  python -m unittest tests.integration.test_native_window.NativeWindowModelTests.test_real_x11_open_draw_close -v
```

## Native C library and desktop shell

The AOT backend supports only its documented verified subset. It is not a
whole-language compiler. `peacock native --library` emits an embeddable library
whose `peacock_run` function returns faults to the host and sends output through
a callback; it does not exit the host process.

```bash
TMP=$(mktemp -d)
./bin/peacock native examples/native.सूत्र --library \
  --keep-c "$TMP/generated" -o "$TMP/libpeacock-host.so"
shells/desktop/build.sh "$TMP/generated" "$TMP/desktop"
"$TMP/desktop/peacock-desktop"
```

On the reference Linux machine this produced an x86-64 position-independent
executable linked to `libpeacock_program.so` and system `libc`/`libm`. Its output
matched `examples/native.सूत्र` on the VM byte-for-byte. C `ctypes` tests also
verify callback failure (`PE5002`) and recoverable Sanskrit assertion failure
(`PE4010`). Standalone executable behavior remains available without `--library`.

## Android shell (SDK verification pending)

`shells/android` contains a Gradle application, manifest, native `Activity`,
JNI bridge and CMake target. The app displays UTF-8 output in native widgets,
runs on a background thread, and requests no network permission.

```bash
shells/android/prepare.sh                 # optional argument: another native-subset .सूत्र
cd shells/android
gradle assembleDebug                      # requires local Gradle + Android SDK/NDK/CMake
```

Preparation runs the real PEACOCK compiler and retains `program.c`, `runtime.c`
and headers under the ignored generated directory. Generated C/runtime pass
strict host C syntax checks here. **No JNI compilation, APK assembly, install,
emulator launch or Android UI execution was available**, so the shell is not
marked device-supported. Managed/connected min/max API tests remain required.

## iOS shell (Xcode verification pending)

`shells/ios` contains SwiftUI, an Objective-C `NSData`/`NSError` bridge, bundle
metadata and a simulator build script.

```bash
shells/ios/prepare.sh                     # generates the C sources on any host
# On macOS with full Xcode and an iOS Simulator SDK:
shells/ios/build-simulator.sh
```

No Apple toolchain exists here. **No `.app` was built or launched, and no device
signing, framework packaging or App Store validation is claimed.** Device builds
need an appropriate Xcode project/signing workflow even though the simulator
script intentionally performs no signing.

## PEACOCK-controlled HTTP servers

Independent of the fixed frame/UI development servers, `.सूत्र` programs can own
a synchronous HTTP socket through `सेवक`:

```bash
./bin/peacock run examples/http_server.सूत्र --grant सञ्जाल
# POST UTF-8 text to the printed 127.0.0.1 port; this example serves one request.
```

`सेवक.श्रृणु`, `स्वीकुरु`, `प्रत्युत्तरय`, `द्वार`, `पिदध्मि` provide listen,
accept, respond, actual-port and close operations. Requests are bounded records
`[id, method, target, headers-json, body]`; there is one outstanding request per
server. Limits are 16 KiB headers and 1 MiB UTF-8 bodies. Chunked requests,
pipelining, TLS, authentication and binary bodies are not implemented. A real
POST/201 Sanskrit response test passes. Host-owned handles are closed on CLI
cleanup; explicit `पिदध्मि` and `अन्ते` should be used for application cleanup.
