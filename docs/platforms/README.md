# Platform hosts

PEACOCK separates the language runtime from presentation. A host embeds the VM
and presents `Canvas` frames through a `Backend`:

| Backend | What it does | Status |
|---|---|---|
| `HeadlessBackend` | keeps the latest frame, optionally writes PNG frames | implemented |
| `WebBackend` | writes PNGs, `latest.png`, `manifest.json`, static `index.html` | implemented; reachable from `.pac` with `--present DIR` |
| `ServerBackend` | stdlib HTTP server for viewer, `/frame.png`, `/manifest.json`, `/healthz` | implemented; reachable from `.pac` with `--serve PORT` |
| Desktop shell | native window + input | not implemented |
| Android shell | SDK/NDK + JNI/ABI bridge + packaging | not implemented |
| iOS shell | Swift/Objective-C host, signing | not implemented (requires macOS/Xcode) |
| WASM host | browser runtime + ABI | not implemented |

This frame-oriented `WebBackend` is distinct from the PEACOCK-authored static
application website at [`website/site.pac`](../../website/site.pac), which exports
twelve routes as HTML/CSS/SVG through the actual CLI. It is a site generator,
not a VM platform target or general interactive browser runtime; see
[`website/README.md`](../../website/README.md).

## Usage

```python
from peacock.frontend.canvas import Canvas
from peacock.frontend.colour import Color
from peacock.platforms import WebBackend

backend = WebBackend("out/preview", title="Demo")
canvas = Canvas(640, 360)
canvas.gradient([Color.from_srgb(0.1, 0.8, 0.9), Color.from_srgb(0.6, 0.1, 0.9)], 30)
backend.present(canvas)
backend.close()
```

```python
from peacock.platforms import ServerBackend

with ServerBackend(host="127.0.0.1", port=8080) as host:
    host.present(canvas)
    input("serving at " + host.url)
```

## Presenting from a `.pac` program

`graphics.present(canvas)` is now a native with the `ui` capability. The CLI
attaches a `WebBackend` with `--present DIR`:

```bash
./bin/peacock run examples/present.pac --grant ui --present out/preview
./bin/peacock run examples/present.pac --grant ui --serve 8099 --linger 30
```

With `--present` each call writes a frame, updates `latest.png`/`index.html` and
is recorded in the manifest when the run ends; with `--serve` the latest frame is
served over HTTP. An embedding host can attach any object with a
`present(canvas)` method through `HostPolicy(presenter=...)` and use
`ServerBackend`, a headless recorder or a future window shell behind the same
native.

## Honest limitations

* There is **no frame clock, input, vsync or display query**. A program presents
  when it calls the native; animation is a loop the program writes itself.
* `--serve PORT` serves the live frame while the program runs and for
  `--linger SECONDS` afterwards; `--linger -1` keeps serving until interrupted.
  The server has no TLS, authentication, input or multi-tenant isolation; bind to
  `127.0.0.1` unless you are inside a container preview.
* Frames are full RGBA8 PNGs; there is no diffing, video encoding or GPU path.
* No mobile target may be claimed until it builds and runs on a device/emulator.

The HTTP server has no authentication or TLS; bind to localhost or put it behind
a hardened proxy.
