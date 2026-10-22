# CPython repository inspection — 2026-10-22

## Source and method

After the native/UI/agent expansion, the upstream repository was cloned from
<https://github.com/python/cpython.git> and inspected locally at exact commit
**`ab2c947f435748d2b8e6d4ea550168a4cff473e5`** (`2026-10-22T10:06:49-07:00`,
`gh-94808: add tests covering PySequence_[InPlace_]Repeat (#99196)`).
This is a pinned architectural comparison, not a claim to track CPython main.
No CPython implementation code was copied into PEACOCK.

The inspection covered `Python/import.c`, `Python/ceval.c`,
`Python/bytecodes.c`, `Objects/dictobject.c`, `Objects/unicodeobject.c`,
`Python/gc.c`, `Modules/_threadmodule.c`, the reference grammar/documentation,
`Platforms/Android`, `Platforms/Apple/iOS`, `Doc/using/ios.rst`, build/CI files,
and `Lib/test`. The checkout had 392 top-level `Lib/test/test_*.py` modules.
The inspected core files are themselves large: 5,677 lines in `import.c`,
8,637 in `dictobject.c`, 15,502 in `unicodeobject.c`, and 2,903 in
`_threadmodule.c`. Those numbers are scope evidence, not a metric PEACOCK should
try to match mechanically.

## Findings and actions

| Area | CPython evidence inspected | PEACOCK consequence |
|---|---|---|
| Exceptions and cleanup | `try/finally` reference semantics; exception-match, import and cleanup bytecode paths | **Implemented after inspection:** Sanskrit `अन्ते`, verified `FINALLY_BEGIN/END/RESUME`, saved error/return/jump completions, nested cleanup stacks and self-host parser parity. Eight focused execution tests cover normal, throw, catch failure, return, break/continue, nesting and supersession. Fatal host aborts remain outside catchable cleanup semantics. |
| Embedding | iOS requires an embedded interpreter/application boundary rather than a system interpreter | Added `peacock_run` to the native AOT C subset: output callback, recoverable error string, no process exit at the library boundary. Desktop execution and C `ctypes` success/fault tests pass. |
| User imports | `Python/import.c`, import locks/state and `Lib/importlib` | **Still missing:** PEACOCK `उपयोग` imports standard namespaces only; there is no user-file module loader, cycle handling, package cache or isolated module state. This is a high-priority next capability, not a solved problem. |
| Built-in containers/object model | dictionary, sequence, set, object and reference-count implementations | **Still missing:** dictionaries/maps, tuples, sets, user classes/protocols, weak references and a language-owned GC. Lists/structs/ranges/tensors are not CPython-equivalent object coverage. |
| Unicode | `Objects/unicodeobject.c`, Unicode databases and tests | PEACOCK has NFC identifiers, code-point strings and Unicode decimal digits. Full Unicode databases, grapheme segmentation, complex-script shaping, locale/collation and normalization APIs remain incomplete. X11 core-font output is not a complete shaping stack. |
| Concurrency | interpreter state, thread module, eval loop and atomic/critical-section machinery | No PEACOCK threads, async/await executor, process isolation API, channel model or deterministic scheduler is implemented; related keywords remain reserved. |
| Standard library and packaging | `Lib`, `venv`, packaging/install configuration and 392 top-level test modules | PEACOCK has focused native libraries but no CPython-scale stdlib, package manager, virtual environments, compatibility matrix or extension-module ecosystem. No completeness claim is made. |
| Android verification | managed/connected emulator tests, min/max API testbeds and third-party test modes | The Android shell now has real Activity/JNI/C sources, but this environment has no SDK/emulator. An APK, UI output, lifecycle behavior and min/max devices remain unverified. |
| iOS packaging/runtime | embedded app model, simulator/device distinction, framework/signing restrictions | The iOS shell has SwiftUI/Objective-C/C sources and a simulator build script, but Xcode is unavailable. No `.app`, simulator launch, device signing or App Store packaging is claimed. |
| Platform CI | reusable Linux/macOS/Windows/WASI/Emscripten/sanitizer workflows | Current new evidence is Linux x86-64 only. Cross-OS, sanitizer, mobile, display and GPU jobs remain required before broad support claims. |

## Boundaries after the audit

`अन्ते` is intentionally **not** yet in the native AOT opcode subset; unsupported
constructs fail before C compilation. The verified native library ABI does not
make the whole Python VM independent or mobile-ready. Likewise, CPython's scope
is not a target that can honestly be closed in one change: user modules,
language-owned memory management, containers, concurrency, Unicode data,
packaging and platform CI remain substantial engineering programmes.

The next highest-value language work is a sandboxed user-module loader with
cycle diagnostics and deterministic verified images, followed by map/container
support and broader Unicode operations. These are recorded as pending rather
than silently marked complete.
