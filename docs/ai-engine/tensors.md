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
* **Serialisation:** `.pkm` v1 with a versioned header, parameter table, float32
  payload, metadata and SHA-256; `quantize_tensor`/`quantization_report` provide
  int8 size/error analysis. Quantised models are not an executable artifact
  format yet.

Gradient checks: tests compare analytic gradients to central finite differences
for matmul/softmax/MSE and a small MLP, with tolerances appropriate to Float32.
That is numerical evidence, not a proof.

Limits: one input/output per declared model, Dense layers only, small datasets,
no convolution/attention/GPU. Trainable tensors require the `compute` capability.
