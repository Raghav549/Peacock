"""Reproducible benchmark suite for the PEACOCK bootstrap toolchain.

These measurements characterise *this* reference implementation on *this*
machine. They are not comparisons against other languages or frameworks, and the
reference engine's pure-Python arithmetic is not representative of the planned
native backend. See research/benchmark-methodology.md.
"""

from __future__ import annotations

import gc
import io
import json
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from peacock.compiler.pipeline import compile_source
from peacock.frontend.canvas import Canvas
from peacock.frontend.colour import Color, palette
from peacock.frontend.easing import ease
from peacock.frontend.png import encode_png
from peacock.frontend.spring import SpringConfig, settle
from peacock.intelligence.datasets import xor_dataset
from peacock.intelligence.evaluation import accuracy_score
from peacock.intelligence.layers import build_model
from peacock.intelligence.tensor import Tensor, matmul, softmax
from peacock.intelligence.training import cross_entropy_loss, train_model
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Result:
    category: str
    name: str
    value: float
    unit: str
    note: str = ""
    samples: int = 1


@dataclass
class BenchReport:
    environment: dict
    results: list[Result] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "environment": self.environment,
            "results": [r.__dict__ for r in self.results],
            "notes": list(self.notes),
        }


LOOP_SOURCE = """module vm_loop
fn main() -> Unit {
    let mut i = 0;
    let mut acc = 0;
    while i < 20000 {
        acc += i;
        i += 1;
    }
    print(str(acc));
}
"""


def _time_call(fn, repeats: int = 5) -> float:
    samples = []
    for _ in range(repeats):
        gc.collect()
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def _median_true(repeats: int, fn) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def _synthetic_source(functions: int) -> str:
    lines = ["module synthetic", ""]
    for i in range(functions):
        lines.append(f"fn f{i}(x: Int) -> Int {{ return x * {i + 1} + {i}; }}")
    lines.append("")
    lines.append("fn main() -> Unit {")
    lines.append(f"    print(str(f0({functions})));")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _run_image(image: dict) -> tuple[int, float]:
    stdout = io.StringIO()
    vm = VM(image, HostPolicy(grants=frozenset({"compute", "fs"}), root=str(REPO_ROOT)), stdout=stdout)
    result = vm.run()
    return result.steps, result.elapsed_seconds


def environment_info() -> dict:
    info = {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": __import__("os").cpu_count(),
        "total_ram_bytes": _total_ram(),
        "gpu": "none detected (no nvidia-smi; CPU-only reference engine)",
    }
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        info["git_commit"] = commit or "unknown"
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        info["git_dirty"] = bool(dirty)
    except (OSError, subprocess.SubprocessError):
        info["git_commit"] = "unknown"
        info["git_dirty"] = None
    return info


def _total_ram() -> int | None:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def run_benchmarks(quick: bool = False) -> BenchReport:
    report = BenchReport(environment_info())
    repeats = 3 if quick else 5
    report.notes = [
        "All measurements are in-process wall-clock medians on the machine listed in environment.",
        "The reference engine is pure Python; arithmetic throughput is not representative of native PEACOCK.",
        "Rendering measurements are for the software rasteriser with 4x4 coverage anti-aliasing.",
        "No results here compare PEACOCK to another language; methodology requires fair, reproducible comparisons.",
    ]

    # -- compilation -------------------------------------------------------
    sources = {}
    for name, path in (
        ("hello", REPO_ROOT / "examples" / "hello.pac"),
        ("tour", REPO_ROOT / "examples" / "tour.pac"),
        ("selfhost-tokenizer", REPO_ROOT / "selfhost" / "tokenizer.pac"),
    ):
        sources[name] = path.read_text(encoding="utf-8")

    for name, source in sources.items():
        result_box = {}

        def compile_once():
            result_box["r"] = compile_source(source, f"{name}.pac")

        ms = _time_call(compile_once, repeats) * 1000.0
        compiled = result_box["r"]
        if not compiled.ok:
            report.results.append(Result("compiler", f"compile_{name}", float("nan"), "ms", "compile failed"))
            continue
        report.results.append(
            Result(
                "compiler",
                f"compile_{name}",
                ms,
                "ms",
                f"{len(source.splitlines())} lines -> {compiled.stats.get('instructions')} instructions",
                repeats,
            )
        )

    synthetic = _synthetic_source(200)
    ms = _time_call(lambda: compile_source(synthetic, "synthetic.pac"), repeats) * 1000.0
    report.results.append(
        Result(
            "compiler",
            "compile_200_functions",
            ms,
            "ms",
            f"{len(synthetic)} bytes, {len(synthetic.splitlines())} lines",
            repeats,
        )
    )

    # Parse throughput (lexing included).
    parse_sample = _synthetic_source(400)
    tokens_count = len(parse_sample.split())
    ms = _time_call(lambda: compile_source(parse_sample, "synthetic2.pac"), repeats) * 1000.0
    report.results.append(
        Result(
            "compiler",
            "compile_throughput",
            (len(parse_sample) / 1024.0) / (ms / 1000.0),
            "KiB/s",
            "synthetic 400-function module, full pipeline",
            repeats,
        )
    )

    # Peak memory for compilation (tracemalloc, separate from timing).
    tracemalloc.start()
    compile_source(sources["selfhost-tokenizer"], "tokenizer.pac")
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report.results.append(
        Result(
            "compiler",
            "compile_peak_memory_tokenizer",
            peak / (1024.0 * 1024.0),
            "MiB",
            "tracemalloc peak during full pipeline",
        )
    )

    # -- VM ---------------------------------------------------------------
    loop_result = compile_source(LOOP_SOURCE, "loop.pac")
    if loop_result.ok:
        steps, seconds = _run_image(loop_result.image)
        report.results.append(
            Result("runtime", "vm_loop_execution", seconds * 1000.0, "ms", f"{steps} bytecode steps", 1)
        )
        report.results.append(
            Result("runtime", "vm_steps_per_second", steps / seconds, "steps/s", "tight integer loop", 1)
        )
    hello_image = compile_source(sources["hello"], "hello.pac").image

    def start_vm():
        _run_image(hello_image)

    ms = _time_call(start_vm, repeats) * 1000.0
    report.results.append(Result("runtime", "startup_hello", ms, "ms", "load image + VM + run", repeats))

    # -- tensors & autodiff ------------------------------------------------
    a = Tensor.rand_uniform((48, 48), seed=1)
    b = Tensor.rand_uniform((48, 48), seed=2)
    ms = _median_true(max(3, repeats), lambda: matmul(a, b)) * 1000.0
    flops = 2 * 48**3
    report.results.append(
        Result("intelligence", "matmul_48x48", ms, "ms", f"{flops} FLOPs, reference Python kernel", max(3, repeats))
    )
    report.results.append(
        Result("intelligence", "matmul_mflops", flops / (ms / 1000.0) / 1e6, "MFLOP/s", "same run", max(3, repeats))
    )

    big = Tensor.rand_uniform((128, 128), seed=3)
    ms = _median_true(max(3, repeats), lambda: softmax(big)) * 1000.0
    report.results.append(Result("intelligence", "softmax_128x128", ms, "ms", "last-axis softmax", max(3, repeats)))

    mlp = build_model((16,), (4,), [(32, "relu"), (4, "linear")], seed=7)
    features = Tensor.rand_uniform((16, 16), seed=9)
    labels = Tensor.from_nested([[1.0, 0.0, 0.0, 0.0]] * 16, dtype="Float32")

    def fwd_bwd():
        mlp.zero_grad()
        loss = cross_entropy_loss(mlp.forward(features), labels)
        loss.backward()
        return loss

    ms = _median_true(max(3, repeats), fwd_bwd) * 1000.0
    report.results.append(
        Result(
            "intelligence",
            "mlp_train_step",
            ms,
            "ms",
            "batch 16, 16->32->4, forward + cross-entropy + backward",
            max(3, repeats),
        )
    )

    dataset = xor_dataset()
    model = build_model((2,), (2,), [(8, "relu"), (2, "linear")], seed=7)
    training = train_model(
        model, dataset, epochs=100, learning_rate=0.05, batch_size=4, seed=7
    )
    report.results.append(
        Result(
            "intelligence",
            "train_xor_100_epochs",
            training.elapsed_seconds * 1000.0,
            "ms",
            f"final loss {training.final_loss:.6f}, accuracy {training.final_accuracy}",
        )
    )
    single = Tensor.from_nested([0.0, 1.0])
    ms = _median_true(200, lambda: model.predict(single)) * 1000.0
    report.results.append(
        Result("intelligence", "inference_latency_single", ms, "ms", "2->8->2 model, reference engine", 200)
    )

    # -- frontend ----------------------------------------------------------
    colors = palette(3, 42)

    def gradient_frame():
        canvas = Canvas(320, 180)
        canvas.gradient(colors, 35.0)
        return canvas

    ms = _time_call(gradient_frame, repeats) * 1000.0
    report.results.append(Result("frontend", "gradient_320x180", ms, "ms", "perceptual gradient fill", repeats))

    def aurora_frame():
        canvas = Canvas(160, 90)
        canvas.aurora(1.5, 42)
        return canvas

    ms = _time_call(aurora_frame, repeats) * 1000.0
    report.results.append(Result("frontend", "aurora_160x90", ms, "ms", "procedural fBm aurora, artistic", repeats))

    encoded = gradient_frame()
    ms = _time_call(lambda: encode_png(encoded), repeats) * 1000.0
    report.results.append(
        Result("frontend", "png_encode_320x180", ms, "ms", "RGBA8, filter 0, zlib level 6", repeats)
    )

    def ui_frame():
        canvas = Canvas(512, 512)
        canvas.clear(Color.from_srgb(0.05, 0.06, 0.12))
        for i in range(20):
            canvas.rect(10.0 + i * 20.0, 40.0, 16.0, 16.0, colors[i % len(colors)])
            canvas.circle(40.0 + i * 20.0, 120.0, 8.0, colors[(i + 1) % len(colors)])
        return canvas

    ms = _time_call(ui_frame, 1 if quick else 3) * 1000.0
    report.results.append(
        Result("frontend", "ui_frame_512x512", ms, "ms", "clear + 20 rects + 20 circles (4x4 AA)", 1 if quick else 3)
    )

    # -- motion ------------------------------------------------------------
    config = SpringConfig(170.0, 26.0, 1.0)
    steps = 2000 if quick else 10000
    start = time.perf_counter()
    settle(0.0, 100.0, config, steps)
    seconds = time.perf_counter() - start
    report.results.append(
        Result("motion", "spring_simulation", steps / seconds, "steps/s", f"{steps} substeps", 1)
    )
    start = time.perf_counter()
    for i in range(100000):
        ease("ease_in_out_cubic", (i % 1000) / 1000.0)
    seconds = time.perf_counter() - start
    report.results.append(
        Result("motion", "easing_calls", 100000 / seconds, "calls/s", "ease_in_out_cubic", 1)
    )

    return report


def format_report(report: BenchReport) -> str:
    lines = []
    lines.append("PEACOCK benchmark results (reference bootstrap engine)")
    lines.append("=" * 78)
    for key in ("python", "platform", "cpu_count", "total_ram_bytes", "git_commit"):
        if key in report.environment:
            value = report.environment[key]
            if key == "total_ram_bytes" and value:
                value = f"{value / (1024**3):.1f} GiB"
            lines.append(f"{key:14s} {value}")
    lines.append("")
    current = None
    for result in report.results:
        if result.category != current:
            current = result.category
            lines.append(f"[{current}]")
        note = f"  ({result.note})" if result.note else ""
        lines.append(f"  {result.name:32s} {result.value:12.3f} {result.unit}{note}")
    lines.append("")
    for note in report.notes:
        lines.append(f"note: {note}")
    return "\n".join(lines)
