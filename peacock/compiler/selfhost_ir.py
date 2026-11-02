"""Differential bridge to the PEACOCK-native IR kernel.

Mirrors `selfhost_types.py` but for the PIR layer. It extracts the Python
IR, renders a PEACOCK program that drives `selfhost/ir.सूत्र` to build the
same IR, executes it on the VM, and compares digests.

This is an oracle adapter, not a second compiler: Python remains
authoritative until broader parity gates are met.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

from peacock.sanskrit import INTERNAL_TO_SOURCE, LEGACY_KEYWORDS

from . import types as T
from .ir import build_ir, IRModule, IRFunction, IRInstr

_MAX_PROBES = 20000
_GENERATED_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

def _native_generated(source: str) -> str:
    def repl(m: re.Match[str]) -> str:
        w = m.group(0)
        return INTERNAL_TO_SOURCE.get(w, LEGACY_KEYWORDS.get(w, w))
    return _GENERATED_WORD.sub(repl, source)

def _type_key(ty: T.Type | None) -> str:
    if ty is None or ty is T.ErrorType:
        return "<error>"
    if isinstance(ty, T.PrimitiveType):
        return ty.name
    if isinstance(ty, T.ListType):
        return f"list<{_type_key(ty.element)}>"
    if isinstance(ty, T.TensorType):
        if ty.shape is None:
            return f"tensor<{ty.dtype},?>"
        return f"tensor<{ty.dtype},{list(ty.shape)}>"
    if isinstance(ty, T.StructType):
        return ty.name
    if isinstance(ty, T.OpaqueType):
        return ty.name
    return str(ty.display() if hasattr(ty, "display") else ty)

def _quote(s: str) -> str:
    e = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t").replace("\0", "\\0")
    return f'"{e}"'

def _escape_for_peacock_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')

# ---------------------------------------------------------------------------
# Python digest (canonical form matching PEACOCK module_digest)
# ---------------------------------------------------------------------------

def _instr_digest_py(instr: IRInstr) -> str:
    op = instr.op
    dest = instr.dest
    args = instr.args
    dest_type = instr.dest_type
    tk = _surface_type_key(dest_type) if dest_type is not None else ""
    dest_part = f" %{dest}" if dest is not None else ""
    if op == "label":
        return f"({op}{dest_part} {args[0]})"
    if op == "jump":
        return f"({op}{dest_part} {args[0]})"
    if op == "branch":
        return f"({op}{dest_part} {args[0]} {args[1]} {args[2]})"
    if op == "return":
        if args[0] is None:
            return f"({op}{dest_part})"
        return f"({op}{dest_part} {args[0]})"
    if op == "throw":
        return f"({op}{dest_part} {args[0]})"
    if op == "const":
        suffix = f" :{tk}" if tk else ""
        if isinstance(args[0], bool):
            return f"({op}{dest_part} {'true' if args[0] else 'false'}{suffix})"
        if isinstance(args[0], str):
            return f"({op}{dest_part} {_quote(args[0])}{suffix})"
        return f"({op}{dest_part} {args[0]}{suffix})"
    if op == "slot_set":
        return f"({op}{dest_part} {args[0]} {args[1]})"
    if op == "slot_get":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]}{suffix})"
    if op == "move":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]}{suffix})"
    if op == "binop":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]} {args[1]} {args[2]}{suffix})"
    if op == "unop":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]} {args[1]}{suffix})"
    if op in ("call", "call_native"):
        callee = _surface_name(args[0]) if args[0] else ""
        joined = ",".join(str(x) for x in args[1]) if len(args) > 1 and isinstance(args[1], (list, tuple)) else ""
        suffix = f" :{_surface_type_key(dest_type)}" if dest_type is not None else ""
        if joined:
            return f"({op}{dest_part} {callee} [{joined}]{suffix})"
        return f"({op}{dest_part} {callee}{suffix})"
    if op == "make_list":
        # args may be tuple of regs
        joined = ",".join(str(x) for x in args) if args else ""
        suffix = f" :{tk}" if tk else ""
        if joined:
            return f"({op}{dest_part} [{joined}]{suffix})"
        return f"({op}{dest_part}{suffix})"
    if op == "make_range":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]} {args[1]}{suffix})"
    if op == "index_get":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]} {args[1]}{suffix})"
    if op == "index_set":
        return f"({op}{dest_part} {args[0]} {args[1]} {args[2]})"
    if op == "field_get":
        suffix = f" :{tk}" if tk else ""
        fname = _surface_name(args[1]) if args[1] else ""
        return f"({op}{dest_part} {args[0]} {fname}{suffix})"
    if op == "field_set":
        fname = _surface_name(args[1]) if len(args) > 1 else ""
        return f"({op}{dest_part} {args[0]} {fname} {args[2]})"
    if op == "len":
        suffix = f" :{tk}" if tk else ""
        return f"({op}{dest_part} {args[0]}{suffix})"
    if op == "assert":
        if len(args) > 1 and args[1] is not None:
            return f"({op}{dest_part} {args[0]} {args[1]})"
        return f"({op}{dest_part} {args[0]})"
    if op == "struct_new":
        joined = ",".join(str(x) for x in args[1]) if len(args) > 1 and isinstance(args[1], (list, tuple)) else ""
        suffix = f" :{tk}" if tk else ""
        sname = _surface_name(args[0]) if args[0] else ""
        if joined:
            return f"({op}{dest_part} {sname} [{joined}]{suffix})"
        return f"({op}{dest_part} {sname}{suffix})"
    if op in ("model_init", "training_method"):
        # model_init: args (model_name, tuple), training_method: (training_name, method, tuple)
        if op == "model_init":
            mname = _surface_name(args[0]) if args[0] else ""
            arg_regs = args[1] if len(args) > 1 else []
            joined = ",".join(str(x) for x in arg_regs) if arg_regs else ""
            suffix = f" :{_surface_type_key(dest_type)}" if dest_type is not None else ""
            if joined:
                return f"({op}{dest_part} {mname} [{joined}]{suffix})"
            return f"({op}{dest_part} {mname}{suffix})"
        else:
            tname = _surface_name(args[0]) if args[0] else ""
            mname = _surface_name(args[1]) if len(args) > 1 else ""
            arg_regs = args[2] if len(args) > 2 else []
            joined = ",".join(str(x) for x in arg_regs) if arg_regs else ""
            suffix = f" :{_surface_type_key(dest_type)}" if dest_type is not None else ""
            if joined:
                return f"({op}{dest_part} {tname} {mname} [{joined}]{suffix})"
            return f"({op}{dest_part} {tname} {mname}{suffix})"
    if op == "method":
        # args: (method_name, receiver, tuple(args))
        mname = _surface_name(args[0]) if len(args) > 0 else ""
        recv = args[1] if len(args) > 1 else ""
        arg_regs = args[2] if len(args) > 2 else []
        joined = ",".join(str(x) for x in arg_regs) if arg_regs else ""
        suffix = f" :{_surface_type_key(dest_type)}" if dest_type is not None else ""
        if joined:
            return f"({op}{dest_part} {mname} {recv} [{joined}]{suffix})"
        return f"({op}{dest_part} {mname} {recv}{suffix})"
    if op in ("try_begin", "finally_begin", "try_end", "finally_end", "finally_resume", "catch"):
        parts = " ".join(str(a) for a in args if a not in (None, ""))
        suffix = f" :{_surface_type_key(dest_type)}" if dest_type is not None else ""
        if parts:
            return f"({op}{dest_part} {parts}{suffix})"
        if suffix:
            # catch with type but no args: "(catch %5 :Type)"
            return f"({op}{dest_part}{suffix})"
        return f"({op}{dest_part})"
    # fallback generic
    parts = " ".join(str(a) for a in args)
    return f"({op}{dest_part} {parts})"

def _surface_name(name: str) -> str:
    # Convert internal identifiers to Sanskrit surface where mapping exists
    # Handles dotted names like "text.is_alpha" -> "पाठ्य.वर्णः"
    if "." in name:
        parts = name.split(".")
        return ".".join(INTERNAL_TO_SOURCE.get(p, p) for p in parts)
    return INTERNAL_TO_SOURCE.get(name, name)

def _surface_type_key(ty) -> str:
    k = _type_key(ty)
    # Surface primitive and opaque type names inside key
    for internal, surface in INTERNAL_TO_SOURCE.items():
        # Replace only whole-word occurrences to avoid partial
        k = re.sub(rf'\b{re.escape(internal)}\b', surface, k)
    return k

def ir_module_digest(ir: IRModule) -> str:
    mod_name = _surface_name(ir.name) if ir.name else ""
    lines = [f"(module {mod_name}"]
    for use in ir.uses:
        lines[0] += f" (use {_surface_name(use)})"
    lines[0] += ")"
    for fn_name, fn in ir.functions.items():
        surf_fn = _surface_name(fn.name)
        surf_ret = _surface_type_key(fn.return_type)
        lines.append(f"(fn {surf_fn} slots={fn.slot_count} ret={surf_ret}")
        for instr in fn.instrs:
            d = _instr_digest_py(instr)
            lines.append(f"  {d}")
        lines.append(")")
    for sname, fields in ir.structs.items():
        surf_s = _surface_name(sname)
        surf_fields = " ".join(_surface_name(f) for f in fields)
        lines.append(f"(struct {surf_s} {surf_fields})")
    return "\n".join(lines)

def _peacock_type_key(ty) -> str:
    return _surface_type_key(ty)

# ---------------------------------------------------------------------------
# Probe emitter: Python IR -> PEACOCK builder calls
# ---------------------------------------------------------------------------

def _emit_ir_module(ir: IRModule) -> list[str]:
    lines: list[str] = []
    mod_name = _surface_name(ir.name) if ir.name else ""
    lines.append(f'    स्थापय mod = new_module({_quote(mod_name)});')
    for use in ir.uses:
        lines.append(f'    module_add_use(mod, {_quote(_surface_name(use))});')
    _counter = 0
    for fn_name, fn in ir.functions.items():
        surf_fn = _surface_name(fn_name)
        bvar = f"b_{fn_name.replace('.','_')}"
        tk = _peacock_type_key(fn.return_type)
        lines.append(f'    स्थापय {bvar} = new_builder({_quote(surf_fn)}, {fn.decl.slot_count}, {_quote(tk)});')
        for instr in fn.instrs:
            _counter += 1
            op = instr.op
            dest = instr.dest
            args = instr.args
            dt = instr.dest_type
            tk2 = _peacock_type_key(dt) if dt is not None else ""
            # generate emit call
            if op == "const":
                val = args[0]
                # render value repr as string
                if isinstance(val, str):
                    vrepr = _quote(val)
                elif isinstance(val, bool):
                    vrepr = _quote("true" if val else "false")
                else:
                    vrepr = _quote(str(val))
                lines.append(f'    emit_const({bvar}, {dest}, {vrepr}, {_quote(tk2)});')
            elif op == "slot_set":
                # args: (slot, reg)
                lines.append(f'    emit_slot_set({bvar}, {args[0]}, {args[1]});')
            elif op == "slot_get":
                lines.append(f'    emit_slot_get({bvar}, {dest}, {args[0]}, {_quote(tk2)});')
            elif op == "move":
                lines.append(f'    emit_move({bvar}, {dest}, {args[0]}, {_quote(tk2)});')
            elif op == "binop":
                lines.append(f'    emit_binop({bvar}, {dest}, {_quote(args[0])}, {args[1]}, {args[2]}, {_quote(tk2)});')
            elif op == "unop":
                lines.append(f'    emit_unop({bvar}, {dest}, {_quote(args[0])}, {args[1]}, {_quote(tk2)});')
            elif op == "call":
                callee = _surface_name(args[0]) if args[0] else ""
                arg_regs = list(args[1]) if len(args) > 1 else []
                arr = f"[{','.join(str(x) for x in arg_regs)}]" if arg_regs else "[]"
                tmp = f"tmp_call_{_counter}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = {arr};')
                lines.append(f'    emit_call({bvar}, {dest if dest is not None else -1}, {_quote(callee)}, {tmp}, {_quote(tk2)});')
            elif op == "call_native":
                callee = _surface_name(args[0]) if args[0] else ""
                arg_regs = list(args[1]) if len(args) > 1 else []
                tmp = f"tmp_call_{_counter}"
                arr2 = f"[{','.join(str(x) for x in arg_regs)}]"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = {arr2};')
                lines.append(f'    emit_call_native({bvar}, {dest if dest is not None else -1}, {_quote(callee)}, {tmp}, {_quote(tk2)});')
            elif op == "branch":
                lines.append(f'    emit_branch({bvar}, {args[0]}, {_quote(args[1])}, {_quote(args[2])});')
            elif op == "jump":
                lines.append(f'    emit_jump({bvar}, {_quote(args[0])});')
            elif op == "label":
                lines.append(f'    emit_label({bvar}, {_quote(args[0])});')
            elif op == "return":
                if args[0] is None:
                    lines.append(f'    emit_return({bvar}, -१);')
                else:
                    lines.append(f'    emit_return({bvar}, {args[0]});')
            elif op == "throw":
                lines.append(f'    emit_throw({bvar}, {args[0]});')
            elif op == "make_list":
                arg_regs = list(args) if args else []
                tmp = f"tmp_elems_{_counter}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in arg_regs)}];')
                lines.append(f'    emit_make_list({bvar}, {dest}, {tmp}, {_quote(tk2)});')
            elif op == "make_range":
                lines.append(f'    emit_make_range({bvar}, {dest}, {args[0]}, {args[1]}, {_quote(tk2)});')
            elif op == "index_get":
                lines.append(f'    emit_index_get({bvar}, {dest}, {args[0]}, {args[1]}, {_quote(tk2)});')
            elif op == "index_set":
                lines.append(f'    emit_index_set({bvar}, {args[0]}, {args[1]}, {args[2]});')
            elif op == "field_get":
                lines.append(f'    emit_field_get({bvar}, {dest}, {args[0]}, {_quote(_surface_name(args[1]))}, {_quote(tk2)});')
            elif op == "field_set":
                lines.append(f'    emit_field_set({bvar}, {args[0]}, {_quote(_surface_name(args[1]))}, {args[2]});')
            elif op == "len":
                lines.append(f'    emit_len({bvar}, {dest}, {args[0]}, {_quote(tk2)});')
            elif op == "assert":
                if len(args) > 1 and args[1] is not None:
                    lines.append(f'    emit_assert({bvar}, {args[0]}, {args[1]});')
                else:
                    lines.append(f'    emit_assert({bvar}, {args[0]}, -१);')
            elif op == "struct_new":
                callee = _surface_name(args[0]) if args[0] else ""
                arg_regs = list(args[1]) if len(args) > 1 and args[1] else []
                tmp = f"tmp_sargs_{_counter}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in arg_regs)}];')
                lines.append(f'    emit_struct_new({bvar}, {dest}, {_quote(callee)}, {tmp}, {_quote(tk2)});')
            elif op == "method":
                mname = _surface_name(args[0]) if args[0] else ""
                recv = args[1]
                arg_regs = list(args[2]) if len(args) > 2 and args[2] else []
                tmp = f"tmp_margs_{_counter}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in arg_regs)}];')
                lines.append(f'    emit_method({bvar}, {dest}, {_quote(mname)}, {recv}, {tmp}, {_quote(tk2)});')
            elif op == "try_begin":
                lines.append(f'    emit_try_begin({bvar}, {_quote(args[0])});')
            elif op == "try_end":
                lines.append(f'    emit_try_end({bvar});')
            elif op == "catch":
                lines.append(f'    emit_catch({bvar}, {dest}, {_quote(tk2)});')
            elif op == "finally_begin":
                lines.append(f'    emit_finally_begin({bvar}, {_quote(args[0])});')
            elif op == "finally_end":
                lines.append(f'    emit_finally_end({bvar}, {_quote(args[0])});')
            elif op == "model_init":
                mname = _surface_name(args[0]) if args[0] else ""
                arg_regs = list(args[1]) if len(args) > 1 and args[1] else []
                tmp = f"tmp_model_{_counter}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in arg_regs)}];')
                lines.append(f'    emit_model_init({bvar}, {dest}, {_quote(mname)}, {tmp}, {_quote(tk2)});')
            elif op == "training_method":
                tname = _surface_name(args[0]) if args[0] else ""
                mname = _surface_name(args[1]) if len(args) > 1 else ""
                arg_regs = list(args[2]) if len(args) > 2 and args[2] else []
                tmp = f"tmp_train_{_counter}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in arg_regs)}];')
                lines.append(f'    emit_training_method({bvar}, {dest}, {_quote(tname)}, {_quote(mname)}, {tmp}, {_quote(tk2)});')
            elif op == "finally_resume":
                lines.append(f'    emit_finally_resume({bvar});')
            else:
                lines.append(f'    // skipped op {op}')
        lines.append(f'    स्थापय kary_{fn_name.replace(".","_")} = builder_finish({bvar});')
        lines.append(f'    module_add_function(mod, kary_{fn_name.replace(".","_")});')
        # verification
        lines.append(f'    निश्चिनु(verify_function(kary_{fn_name.replace(".","_")}) == "");')
    for sname, fields in ir.structs.items():
        surf_s = _surface_name(sname)
        surf_fields = " ".join(_surface_name(f) for f in fields)
        desc = f"(struct {surf_s} {surf_fields})"
        lines.append(f'    module_add_struct(mod, {_quote(desc)});')
    lines.append(f'    मुद्रय(module_digest(mod));')
    return lines

class SelfHostIRMismatch(RuntimeError):
    pass

def shadow_ir_check(source: str, path: str = "<source>") -> dict:
    from .pipeline import compile_source
    from peacock.runtime.vm import VM
    from peacock.runtime.host import HostPolicy
    compiled = compile_source(source, path, optimize_ir=False)
    if not compiled.ok or compiled.typed is None:
        # No IR to check if semantic failed
        return {"ir_cases": 0, "verified": False}
    from .ir import build_ir
    ir = build_ir(compiled.typed, source, path)
    # generate PEACOCK probe
    probe_lines = _emit_ir_module(ir)
    # Wrap into main that uses library
    repo_root = Path(__file__).resolve().parents[2]
    lib_path = repo_root / "selfhost" / "ir.सूत्र"
    library = lib_path.read_text(encoding="utf-8")
    marker = 'कार्य मुख्य() -> एकक {'
    main_start = library.find(marker)
    if main_start < 0:
        raise SelfHostIRMismatch(f"{lib_path} missing main")
    # Build generated main
    gen_main = 'कार्य मुख्य() -> एकक {\n' + "\n".join(probe_lines) + "\n}\n"
    source_combined = library[:main_start] + gen_main
    compiled2 = compile_source(source_combined, "<selfhost-ir-shadow>", optimize_ir=False)
    if not compiled2.ok:
        raise SelfHostIRMismatch("generated IR shadow failed to compile: " + compiled2.diagnostics.render_all(source_combined))
    out = io.StringIO()
    try:
        VM(compiled2.image, HostPolicy(root=str(repo_root), max_steps=10_000_000), stdout=out).run()
    except Exception as exc:
        raise SelfHostIRMismatch(f"PEACOCK IR kernel disagrees: {exc}") from exc
    peacock_digest = out.getvalue().strip()
    py_digest = ir_module_digest(ir).strip()
    if peacock_digest != py_digest:
        raise SelfHostIRMismatch(f"IR digest mismatch:\nPython:\n{py_digest}\n\nPEACOCK:\n{peacock_digest}")
    return {"ir_cases": len(ir.functions), "verified": True}

