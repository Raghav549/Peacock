# Security policy and threat model

PEACOCK executes untrusted `.सूत्र` programs under a capability-based policy. This
document states what is enforced, what is not, and how to report a problem.

## Supported version

Security fixes target the current `0.4.x` reference implementation. There is no
long-term-support branch yet.

## Reporting a vulnerability

Open a **private security advisory** on the repository (GitHub → Security →
Advisories → Report a vulnerability). Do not open a public issue for an unfixed
vulnerability. Include:

* the affected commit/version;
* a minimal `.सूत्र` program or artifact;
* the command and host policy used;
* the observed behaviour and why it violates the model below.

Do not include real secrets or personal data. We will acknowledge the report and
coordinate disclosure.

## Security model

### Capabilities

Four capabilities exist in v0.4:

| Capability | Authority |
|---|---|
| `गणना` | create trainable tensors, autodiff, model init/train/predict, save/load |
| `सञ्चय` | read/write files and create directories inside the host sandbox root |
| `दृश्य` | attach rendered frames or retained UI to a host presentation/event backend |
| `सञ्जाल` | bind/use PEACOCK HTTP server handles and invoke a host-configured LLM agent |

A program must **declare** a capability in each function that performs a
protected operation. The host must **independently grant** it. Declaration is not
authority. The VM checks both before dispatch; `peacock audit` reports static
usage but is not an enforcement mechanism.

`दृश्य` authorizes attachment of a presentation/event host; it grants no clipboard
or display-query API. Local UI queue operations do not themselves open a window.
A host may grant `दृश्य` without attaching a backend; presentation then fails
with `PE4006` before a frame/document is handed to a backend. `सञ्जाल` does not
provide a general URL client or choose LLM credentials/endpoints.

Capability denials raise `PE4001`. They may be caught by PEACOCK code, but a
caught denial grants no authority and the operation does not occur. Panics
(`PE4011`) and resource-limit errors (`PE4003`) cannot be caught.

### Filesystem sandbox

`HostPolicy`:

* resolves relative paths against a root that must exist and be a directory;
* rejects absolute paths outside the root, `..` escapes, and NUL bytes;
* resolves symlinks and requires the final path to remain under the root;
* creates parent directories for writes and permits explicit `सञ्चय.निधिरचना`,
  inside the root;
* enforces `max_file_bytes` on reads and writes;
* requires the `सञ्चय` grant for every operation.

This is **best-effort process-level confinement**, not a kernel sandbox. There is
a time-of-check/time-of-use window between resolution and open; an attacker who
can mutate the filesystem concurrently may exploit it. Do not run untrusted
programs with access to sensitive directories, and use OS-level isolation
(containers, seccomp, landlock, a dedicated user) for multi-tenant use.

### Resource budgets

The host enforces:

| Budget | Default |
|---|---:|
| bytecode steps | 2,000,000 |
| call depth | 128 |
| output characters | 1,000,000 |
| tensor elements | 1,000,000 |
| dataset samples | 200,000 |
| training epochs | 10,000 |
| file bytes | 64 MiB |

Steps, depth, output, tensor, dataset and epoch limits raise `PE4003` and are not
catchable. Some library-level limits (canvas dimensions/pixels) raise faults
inside natives and are catchable; they do not allow allocating beyond the stated
limits. Agent rules, state size and planning expansions are bounded and require
`गणना`; UI node counts, grid columns and text/HTML sizes are bounded; 3-D mesh
resolution, light counts, triangle work and canvas dimensions are bounded. These
are implementation guards, not a complete host-memory quota. UI events are
bounded to 1024 queued records with key/text limits; native HTTP servers are
limited to eight handles, 16 KiB request headers, 1 MiB UTF-8 bodies and bounded
text responses. LLM agents have step, response-byte, tool-output, token and
character budgets, but host tool handlers must implement their own I/O timeouts.
OpenCL operations are limited to 16,777,216 output elements. Grammar corpus,
search and pratyāhāra operations are offline and need no capability.

### Artifacts and models

`.बीज` files are verified structurally, then hashed with SHA-256; `.ज्ञान` model
files have their own versioned header, parameter table, payload size bound and
digest. Loading a malformed or tampered file raises a structured error and does
not execute partial bytecode. `verify_image` checks opcodes, operands, slots,
jump targets, arities, native names, capability names and model references
before the first instruction executes.

The JSON parser used for artifacts is Python's standard library `json`; deeply
nested payloads are bounded by the container length and digest checks. This is
not a formally verified parser.

### Memory and arithmetic

Integer arithmetic is checked; overflow is a fault, not wraparound. Division and
remainder by zero are faults. Bounds are checked. Uninitialised locals are
faults. There is **no independent language-level memory manager or GC API** in
0.4; the CPython host owns VM objects and applies its own reference counting and
cyclic GC outside PEACOCK semantics. The native C subset instead tracks and
releases run-scoped allocations and enforces resource bounds. A program can still consume host
memory within tensor/canvas/server limits; step and element budgets are the
primary mitigations, not a complete process-memory quota.

### External boundaries

* CPython executes the bootstrap and VM. A CPython memory-safety vulnerability is
  outside this project's control.
* `zlib` is used for PNG compression/decompression; the decoder validates sizes,
  CRCs, chunk lengths and filter types, and enforces an expected decompressed
  size before copying.
* `hashlib` provides SHA-256.
* A presentation backend receives in-process `Canvas` objects. Backend
  exceptions are wrapped as `PE5003` host errors; they cannot corrupt VM state.
  The static-web backend writes PNGs and an HTML viewer with no script.
* Frame HTTP hosting (`peacock run --serve`) uses fixed routes and the latest
  presented frame. Interactive `--ui-serve` additionally accepts same-origin
  event POSTs and serves fragments. Neither has authentication, TLS or
  multi-tenant isolation; both bind to `127.0.0.1` by default. Anyone who can
  reach the interactive port may drive program events. Use OS isolation/a
  hardened proxy for deliberate exposure. `--linger -1` requires deliberate
  shutdown.
* PEACOCK-owned `सेवक` sockets are likewise plaintext and unauthenticated. They
  parse bounded HTTP/1.1 text requests but do not implement chunked transfer,
  pipelining or concurrent dispatch. Binding a non-loopback numeric address is
  an explicit source/host decision under `सञ्जाल`, not a safe-production-server
  claim.
* Static web/frame and `दृश्य` HTML exports contain no JavaScript. The explicit
  interactive UI host injects a small same-origin event/refresh script. UI text
  and attributes are escaped and link schemes restricted; exported HTML is data
  for the browser, not an accessibility or windowing sandbox.
* The X11 host uses `ctypes` and core X11 drawing. It requires a trusted working
  display/client library and is not a memory-safe or complex-script-complete
  widget toolkit. No real-display validation was available in this environment.
* LLM responses and tool outputs are untrusted data. The provider requires HTTPS
  remotely, disables redirects and bounds responses; tool schemas/capabilities
  prevent accidental dispatch but do not prove that a requested action is safe.
  Default tools are offline grammar/calculator operations only. API keys come
  from host environment configuration and are excluded from agent traces.
* Native AOT rejects privileged/unsupported opcodes before C compilation. Its C
  runtime checks operations and returns library faults to the host, but generated
  C is not formally memory-safe, is not a sandbox for malicious host tools, and
  the current shared-library state is neither thread-safe nor reentrant.
* `दृश्य.रक्ष` and 3-D output through `चित्र.रक्ष` use the same `सञ्चय`-gated
  `HostPolicy.write_bytes` sandbox as other file writes; they do not open paths
  directly.

## Out of scope / not guaranteed

* formal verification or a proof of the type system, VM or sandbox;
* side-channel resistance (timing, cache, power);
* protection from a malicious **host** (the host can read files and grant
  capabilities arbitrarily);
* protection from a compromised Python interpreter or OS;
* denial of service from heavy but in-budget computation (e.g. large matmuls);
* production-grade multi-tenant isolation;
* verified Android/iOS packages, actual X11/OpenCL hardware behavior, or mobile
  platform store/signing guarantees in the current Linux headless environment;
* safety or semantic correctness of an externally hosted LLM/model.

## Security regression evidence

`tests/security/test_capabilities.py` covers: missing declarations, runtime
denials, caught denials, sandboxed nested directory creation and attempted
`सञ्चय.निधिरचना` escapes, traversal/nested traversal/absolute/Windows-style
paths, NUL bytes, symlink escapes, file-size limits, step/depth/output/tensor/
dataset/epoch limits, unknown grants, panic non-catchability, unknown natives,
unknown capabilities in tampered images, and artifact digest tampering. The
fuzzers (`tests/integration/test_fuzzing.py`, `peacock fuzz`) exercise the lexer,
parser, artifact and model loaders with deterministic malformed inputs. Additional
integration tests cover native-library recoverable faults/output failures,
recoverable finalization, HTTP request limits/capability checks, UI enabled-tree
dispatch, LLM schema/grant/redirect/budget failures and explicit OpenCL fallback
behavior.

A passing test suite is evidence, not a guarantee. Report gaps.
