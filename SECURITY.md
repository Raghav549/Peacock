# Security policy and threat model

PEACOCK executes untrusted `.सूत्र` programs under a capability-based policy. This
document states what is enforced, what is not, and how to report a problem.

## Supported version

Security fixes target the current `0.3.x` reference implementation. There is no
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

Three capabilities exist in v0.3:

| Capability | Authority |
|---|---|
| `गणना` | create trainable tensors, autodiff, model init/train/predict, save/load |
| `सञ्चय` | read/write files and create directories inside the host sandbox root |
| `दृश्य` | hand rendered 2D/3D frames to a host-attached presentation backend |

A program must **declare** a capability in each function that performs a
protected operation. The host must **independently grant** it. Declaration is not
authority. The VM checks both before dispatch; `peacock audit` reports static
usage but is not an enforcement mechanism.

`दृश्य` is presentation-only: it grants no input, window-management, clipboard or
display-query authority. A host may grant `दृश्य` without attaching a backend; the
call then fails with `PE4006` before any data leaves the VM.

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
are implementation guards, not a complete host-memory quota. Grammar corpus,
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
faults. There is **no language-level garbage collector** in 0.3; the Python host
owns memory and cycles are not collected. A program can still consume host
memory within the tensor/canvas limits; step and element budgets are the primary
mitigations.

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
* HTTP hosting (`peacock run --serve`) uses the standard-library server; it
  serves only fixed routes and the latest presented frame. It has no
  authentication, TLS or multi-tenant isolation, binds to `127.0.0.1` by default,
  and should be placed behind a hardened proxy if exposed. `--linger -1` keeps it
  running after the program ends, so it must be stopped deliberately.
* The web viewer and `दृश्य` UI export are static HTML with no JavaScript. UI
  text/attributes are escaped and link schemes are restricted; exported HTML is
  still data for the browser, not a native accessibility or windowing sandbox.
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
* mobile/desktop targets (not implemented).

## Security regression evidence

`tests/security/test_capabilities.py` covers: missing declarations, runtime
denials, caught denials, sandboxed nested directory creation and attempted
`सञ्चय.निधिरचना` escapes, traversal/nested traversal/absolute/Windows-style
paths, NUL bytes, symlink escapes, file-size limits, step/depth/output/tensor/
dataset/epoch limits, unknown grants, panic non-catchability, unknown natives,
unknown capabilities in tampered images, and artifact digest tampering. The
fuzzers (`tests/integration/test_fuzzing.py`, `peacock fuzz`) exercise the lexer,
parser, artifact and model loaders with deterministic malformed inputs.

A passing test suite is evidence, not a guarantee. Report gaps.
