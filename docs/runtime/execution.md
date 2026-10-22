# Runtime execution model

Each VM is a deterministic, single-threaded stack machine. Explicit HTTP and
X11 hosts may use implementation threads outside language execution.

* **Frames:** fixed slot arrays, an operand stack, a program counter with
  source-line entries, active try/finally handlers, cleanup/completion stacks
  and declared capabilities.
* **Values:** Int/Float/Bool/String/Unit/Range are value-like; List, Tensor,
  struct instances, Canvas, Model, Dataset, UI and Agent values are references.
* **Arithmetic:** 64-bit checked integers; binary64 floats; truncated division;
  remainder with the dividend's sign; zero division is a catchable fault.
* **Locals:** reading an uninitialised slot is a fault. `स्थापय` initialises in
  order; there is no hoisting.
* **Calls:** recursion is allowed to the host depth limit. There are no
  closures, user-function default arguments or varargs; native signatures may
  define defaults.
* **Errors:** `VMFault` is catchable; `CapabilityError` is catchable and grants
  nothing; `PanicError` and `ResourceLimitError` terminate the run. Stack traces
  record function, line and column for each frame.
* **Finalization:** `अन्ते` saves normal/error/return/break/continue completions
  and runs cleanup inner-to-outer. Cleanup can supersede the saved completion;
  outer cleanup still unwinds. Fatal panic/resource exits bypass cleanup.
* **Budgets:** steps, call depth, output characters, tensor elements, dataset
  samples, training epochs and file bytes are enforced by `HostPolicy`.
  Interactive UI, HTTP, LLM and OpenCL implementations add their own documented
  queue/byte/step/element limits.
* **Determinism:** execution has no randomness unless a program supplies a seed
  to a dataset/model initialiser. There is no source-level wall-clock API;
  host network/UI events are explicitly external inputs.

Memory: VM values are Python objects managed by CPython, including its own
reference counting/cyclic collector outside PEACOCK semantics. There is no
independent language memory manager or GC API. Native AOT tracks allocations
per run and releases them at normal/fault boundaries. Neither is a complete
process-memory quota.

Artifact loading: `.बीज` magic/version/digest → `verify_image` → execution. A
failure before the first instruction is an artifact error, not a program fault.
