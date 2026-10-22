# Runtime execution model

The VM is a deterministic, single-threaded stack machine.

* **Frames:** fixed slot arrays, an operand stack, a program counter with
  source-line entries, active try handlers and declared capabilities.
* **Values:** Int/Float/Bool/String/Unit/Range are value-like; List, Tensor,
  struct instances, Canvas, Model and Dataset are references.
* **Arithmetic:** 64-bit checked integers; binary64 floats; truncated division;
  remainder with the dividend's sign; zero division is a catchable fault.
* **Locals:** reading an uninitialised slot is a fault. `let` initialises in
  order; no hoisting.
* **Calls:** recursion is allowed to the host depth limit. There are no
  closures, default arguments (except native signatures) or varargs.
* **Errors:** `VMFault` is catchable; `CapabilityError` is catchable and grants
  nothing; `PanicError` and `ResourceLimitError` terminate the run. Stack traces
  record function, line and column for each frame.
* **Budgets:** steps, call depth, output characters, tensor elements, dataset
  samples, training epochs and file bytes are enforced by `HostPolicy`.
* **Determinism:** execution has no randomness unless a program supplies a seed
  to a dataset/model initialiser; no wall-clock API is exposed in 0.1.

Memory: PEACOCK values are Python objects; there is no language-level GC in
0.1. Cycles are not collected and memory is bounded by host/process limits and
the tensor/canvas budgets.

Artifact loading: `.बीज` magic/version/digest → `verify_image` → execution. A
failure before the first instruction is an artifact error, not a program fault.
