# Benchmark methodology

## Purpose

`peacock bench` characterises **this reference implementation on the machine it
runs on**. It is a regression and bottleneck-finding tool, not a leaderboard.
Nothing in this repository may present these numbers as a comparison with another
language, runtime or framework.

## How a run is taken

```bash
./bin/peacock bench --json benchmarks/reference-machine.json
./bin/peacock bench --quick            # fewer repeats, for a smoke check
```

The harness (`peacock/benchmarks.py`):

* records the environment: Python version/build, platform, kernel, CPU count,
  total RAM, git commit, compiler version;
* compiles three checked-in sources (`examples/hello.सूत्र`, `examples/tour.सूत्र`,
  `selfhost/tokenizer.सूत्र`) and a generated 200-function file;
* runs tensor, training, rendering, motion and VM workloads;
* reports the **median** of repeated in-process wall-clock samples;
* uses `time.perf_counter()` (monotonic, high resolution) and `gc.collect()`
  before each timed compile/render sample in `_time_call`;
* uses 5 repeats in full mode and 3 in quick mode for most operations; training,
  the spring simulation and the easing loop are single-shot or fixed-size runs;
* measures inference over 200 calls and reports the median;
* stores the result as JSON with schema version 1 and a UTC timestamp.

`benchmarks/reference-machine.json` is checked in as evidence and regenerated
only by the command above. `benchmarks/latest.json` is a scratch output and is
ignored.

## Reference machine

Recorded in the JSON (`environment` block). At the 2026-10-17 checkpoint:

* CPython 3.11.2, Linux 6.1.158, x86-64;
* 2 vCPU, 3.8 GiB RAM, no GPU, no swap pressure observed;
* repository commit `755fbc8` (the initial commit; all v0.1 work is uncommitted
  in the working tree and the JSON records the commit it was built from);
* no other workloads intentionally running during the run.

## What each category measures

| Category | Workload | What the number means |
|---|---|---|
| `compiler` | compile hello/tour/tokenizer/synthetic 200 functions | full pipeline (lex → parse → check → IR → optimise → emit), source already in memory |
| `compiler` | `compile_200_functions_bytes` | emitted image size |
| `compiler` | `throughput_kib_s` | source KiB per second for the synthetic file |
| `compiler` | `tokenizer_peak_mib` | `tracemalloc` peak for the largest compile |
| `runtime` | `startup_hello` | load image + create VM + execute hello |
| `runtime` | `vm_loop_*` | dispatch of a counted loop; steps/s is VM dispatch, not arithmetic |
| `intelligence` | `matmul_48x48` | 2·48³ FLOPs divided by median time; pure-Python kernel |
| `intelligence` | `softmax_128x128`, `mlp_train_step` | elementwise/reduction workloads |
| `intelligence` | `train_xor_100_epochs` | end-to-end training of a 2→8→2 MLP |
| `intelligence` | `inference_latency_single` | one forward pass, median of 200 |
| `frontend` | `gradient_320x180`, `aurora_160x90` | software raster fill and procedural fBm |
| `frontend` | `png_encode_320x180` | RGBA8 PNG encode at zlib level 6 |
| `frontend` | `ui_frame_512x512` | clear + 20 rects + 20 circles with 4×4 AA |
| `motion` | `spring_simulation` | integrate 10 000 substeps |
| `motion` | `easing_calls` | 100 000 cubic easing evaluations |

## Limitations (read before quoting a number)

1. **In-process, interpreter-bound.** Python object overhead dominates. Numbers
   do not predict native or GPU performance and must not be extrapolated.
2. **Small samples.** Medians of 3–5 samples have wide uncertainty; no confidence
   intervals, outlier analysis or effect sizes are reported. The methodology
   literature [georges2007statistically], [hoefler2015scientific] sets a higher bar.
3. **No isolation.** CPU frequency scaling, JIT/GC state (CPython has no JIT),
   background processes and thermal state are uncontrolled. `gc.collect()` before
   samples reduces but does not remove variance.
4. **Warm cache.** Sources are read before timing; file I/O is excluded.
5. **Compilation includes everything** except reading the file from disk.
6. **Float32 storage / binary64 compute** (ADR-0009) affects tensor throughput
   relative to native libraries.
7. **Rendering is not a frame loop.** No compositor, text, input or display
   present; `ui_frame` is shapes into a buffer.
8. **No memory-leak measurement.** Only one tracemalloc peak is recorded.
9. **One machine, one OS.** No cross-platform or cross-version comparison.
10. **Not statistically rigorous.** Treat differences under ~10 % as noise.

## Rules for reporting

* Name the implementation (Python bootstrap), the commit, the machine and the
  exact command.
* Quote units and sample counts; do not round a median into an unqualified
  "faster".
* Never place PEACOCK and another implementation in the same table unless the
  workload, input, hardware and measurement method are identical and the
  comparison is the explicit goal of a documented study.
* Do not claim a speedup from a code change without before/after JSON from the
  same machine and a repeated run.
* Do not use benchmarks to imply readiness for production, mobile or GPU.
* Keep `benchmarks/reference-machine.json` reproducible; if the harness changes,
  regenerate and note the schema change.

## Reproducing

```bash
python3 --version                    # 3.11+
git rev-parse --short HEAD
./bin/peacock bench --json benchmarks/latest.json
python3 - <<'PY'
import json
r = json.load(open("benchmarks/latest.json"))
for x in r["results"]:
    print(f'{x["category"]:12} {x["name"]:28} {x["value"]:10.3f} {x["unit"]}')
PY
```

Compare the environment block before comparing numbers. A result from a
different CPU, Python build or commit is a different measurement.
