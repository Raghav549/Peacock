# Intelligence engine

`peacock/intelligence/` is an original CPU implementation with no NumPy/PyTorch.

* **Storage:** flat Python lists plus a shape tuple. Dtypes: Bool, Int32,
  Float32, Float64. Float32 rounds on construction/storage; arithmetic uses
  binary64 before storage (documented deviation).
* **Ops:** broadcasting, elementwise arithmetic, matmul (rank 2), reductions,
  reshape, transpose, select rows, softmax/log-softmax, activations.
* **Autodiff:** reverse-mode; each op records parents and a backward closure.
  `backward()` topologically sorts the graph and accumulates gradients;
  `zero_grad()` clears them. Non-scalar outputs need an explicit gradient.
* **Training:** Dense/Sequential/Model, SGD (optional momentum) and Adam,
  mini-batches, cross-entropy/MSE, finite-loss checks, deterministic seeding,
  per-epoch losses/accuracies and a report with dataset provenance.
* **Evaluation:** accuracy, confusion matrix, per-class precision/recall/F1.
* **Serialisation:** `.ज्ञान` v1 with a versioned header, parameter table, float32
  payload, metadata and SHA-256; `quantize_tensor`/`quantization_report` provide
  int8 size/error analysis. Quantised models are not an executable artifact
  format yet.

Gradient checks: tests compare analytic gradients to central finite differences
for matmul/softmax/MSE and a small MLP, with tolerances appropriate to Float32.
That is numerical evidence, not a proof.

Limits: one input/output per declared model, Dense layers only, small datasets,
and no convolution/attention layers. Trainable tensors require the `गणना`
capability. Accelerated operations below are separate from autodiff/training and
do not provide GPU gradients or GPU model execution.

## Compute backends (0.4)

`peacock/intelligence/gpu.py` and the `गणनयन्त्र` native namespace expose a CPU
reference backend and a real OpenCL 1.2 backend without NumPy/PyTorch. Supported
operations are equal-shape Float32/Float64 addition, multiplication, ReLU and
compatible rank-2 matrix multiplication. OpenCL returns Float32 tensors.

```bash
./bin/peacock run examples/gpu.सूत्र --grant गणना
# "स्वतः" selects OpenCL when usable and otherwise CPU.
# "त्वरक" explicitly requires an OpenCL GPU/accelerator; it never falls back.
# "क्रमक" explicitly selects CPU.
```

`गणनयन्त्र.पश्चात्तन्त्राणि()` lists usable backend names;
`गणनयन्त्र.विवरण(name)` reports backend/device/vendor/version and whether this is
hardware. `संकलय`, `गुणय`, `धनाङ्क` and `आव्यूहगुणन` perform the operations.

The OpenCL path dynamically loads the platform driver, enumerates actual GPU or
accelerator devices, compiles four kernels, allocates device buffers, enqueues
work, waits and reads results. Each operation is synchronous and bounded to
16,777,216 output elements; contexts and per-operation resources are released.
Matrix multiplication validates `[m,k] × [k,n]`, not equal elementwise shapes.

CPU operation tests pass, including non-square matrix multiplication. The
OpenCL hardware parity test is **skipped in the current environment because no
OpenCL device/driver is available**. Source presence, CPU fallback and kernel
text are not evidence of GPU execution. CUDA, Metal, Vulkan, asynchronous
streams, device-resident tensor graphs and distributed compute are not
implemented.
