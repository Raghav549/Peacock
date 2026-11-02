"""Differential bridge to the PEACOCK-native optimiser kernel.

Mirrors `selfhost_ir.py` / `selfhost_bytecode.py` but for `peacock/compiler/optimizer.py`.
Stage-4c partial: kernel (`selfhost/optimizer.सूत्र`) implements constant folding
(int arithmetic with 64-bit overflow, string +), branch folding on const bool,
and jump-to-next-label peephole. Full parity (reachability/DCE/tensor) planned.

The oracle is `Optimizer.optimize_module`; the PEACOCK kernel is `selfhost/optimizer.सूत्र`.
"""
from __future__ import annotations
import io
from pathlib import Path
from .optimizer import optimize as py_optimize
from .ir import build_ir

def _ir_digest(mod) -> str:
    # reuse ir digest logic from selfhost_ir
    from .selfhost_ir import ir_module_digest
    return ir_module_digest(mod)

def shadow_optimizer_check(source: str, path: str = "<source>") -> dict:
    from .pipeline import compile_source
    from peacock.runtime.vm import VM
    from peacock.runtime.host import HostPolicy
    compiled = compile_source(source, path, optimize_ir=False)
    if not compiled.ok or compiled.typed is None:
        return {"optimized": False}
    ir = build_ir(compiled.typed, source, path)
    # Python optimizer
    import copy
    ir_copy = copy.deepcopy(ir)
    _, py_stats = py_optimize(ir_copy)
    py_digest = _ir_digest(ir_copy).strip()
    # PEACOCK optimizer probe would go here (emit IRModule -> optimize_module -> digest)
    # For now, compare stats shape only; full digest parity is pending implementation
    # of the probe emitter (similar to _emit_ir_module but wrapped with optimize_module call).
    return {"optimized": True, "py_stats": py_stats, "py_digest_prefix": py_digest[:200]}
