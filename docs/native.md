# Native ahead-of-time compilation

`peacock.native` compiles a **verified bytecode subset** to direct C control flow
and then invokes the host C compiler. It is not a bytecode-array interpreter in
disguise: generated functions contain C statements and labels, calls to other
generated functions, and a small checked value runtime. The VM remains the
reference implementation for the full language.

## Commands

```bash
# Standalone executable
./bin/peacock native examples/native.सूत्र -o /tmp/peacock-native
/tmp/peacock-native

# Embeddable shared library and retained C sources
./bin/peacock native examples/native.सूत्र --library \
  --keep-c /tmp/peacock-c -o /tmp/libpeacock-example.so
```

Deterministic generated source records the language/compiler versions. The
builder uses an argument vector rather than a shell command, writes within an
owned build directory, and enables strict warnings. A host C compiler and
platform shared-library support are required for binary builds.

## Implemented subset

* signed 64-bit integers, finite doubles, booleans, unit and UTF-8 strings;
* lists, ranges, indexing and list assignment;
* user function calls, lexical slots, arithmetic/comparison/logical operators,
  branches, loops and returns;
* `मुद्रय`, `पाठ्य`, `दैर्घ्य` natives;
* the implemented length/list/string methods: `दैर्घ्य`, `योजय`, `निष्कासय`,
  `प्राप्नु`, `अस्ति`, `अनुक्रम`, `संयोजय`, `क्रमय`, `विपरीतय`, `आरभ्यते`,
  `अन्त्यते`, `उपपाठ्य`;
* assertions and top-level thrown errors as checked native faults;
* `PE` diagnostics, call/stack/step/resource bounds, and checked integer division,
  indexing, allocation and conversion.

Unsupported opcodes, natives, methods, model/training declarations and constant
types fail **before C compilation**. In particular, general `यत्न`/`गृह्ण`/
`अन्ते` unwinding, maps/objects, UI, HTTP, tensors, GPU, modules and the complete
VM native library are not silently AOT-compiled. Run those programs on the VM.
The subset will expand only with matching semantic and runtime tests.

## Shared-library ABI

`--library` emits `peacock_run` and installs `include/peacock_native.h`:

```c
int peacock_run(int64_t max_steps,
                POutputCallback output,
                void *userdata,
                const char **error_message);
```

The host supplies a callback receiving `(bytes, length, userdata)`. Success
returns `0`; a PEACOCK fault or failed output callback returns `3`. The optional
error pointer is NUL-terminated and remains owned by the library until the next
run. Runtime state and output callbacks are reset for every invocation. Native
allocations are tracked per run and released on both normal and fault returns;
`p_runtime_allocation_count()` is zero after the tested calls. A fault unwinds to
`peacock_run`; it does not call `exit()` in the embedding process.

The current runtime uses process-global state: calls are **not thread-safe or
reentrant**, and one library instance must be entered serially. Run-scoped
allocation tracking is not a tracing garbage collector or a general public
memory-management API. Generated
functions are native code, but this ABI is not a stable cross-version plugin
interface yet.

## Executed verification

`tests/integration/test_native_aot.py` builds and executes real C binaries and a
shared library. Eight tests cover source generation, strict native builds,
VM-identical output, unsupported-opcode rejection, deterministic output, callback
failure, recoverable assertion faults and zero live allocations after repeated
success/fault runs. The example also completed under AddressSanitizer and
UndefinedBehaviorSanitizer with leak detection enabled. The desktop shell adds
an independent host executable around the same ABI; see
[platform hosts](platforms/README.md).

These results do not imply that arbitrary PEACOCK programs are AOT-compatible,
nor that cross-compiled mobile binaries have been executed.
