"""Differential bridge to the PEACOCK-native bytecode kernel.

Mirrors `selfhost_ir.py` but for the bytecode layer. Python remains
authoritative; this module drives `selfhost/bytecode.सूत्र` and compares
its bytecode image digest with `peacock/compiler/bytecode.py`.

Stage-5 partial: kernel (`selfhost/bytecode.सूत्र`) is complete with
8 builtin checks (const/binop/branch/call/try/finally/field/len/module).
The shadow oracle is implemented for the core subset and is being
extended to the full 16-file corpus (currently hello/tour validated,
remaining fixtures tracked in tests/integration/test_selfhost_bytecode.py).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from peacock.sanskrit import INTERNAL_TO_SOURCE

from .bytecode import compile_bytecode
from .ir import build_ir

_MAX_PROBES = 20000

def _escape_peacock_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _quote(s: str) -> str:
    e = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{e}"'


def _surface_name(name: str) -> str:
    if "." in name:
        return ".".join(INTERNAL_TO_SOURCE.get(p, p) for p in name.split("."))
    return INTERNAL_TO_SOURCE.get(name, name)


def _bytecode_digest_py(image: dict) -> str:
    """Canonical digest matching PEACOCK bc_module_digest."""
    lines = [f"(module {_surface_name(image.get('module',''))}"]
    uses = image.get("uses", [])
    if uses:
        # first line includes uses
        pass
    # Build first line with uses
    first = f"(module {_surface_name(image.get('module','') or '')}"
    for u in image.get("uses", []):
        first += f" (use {_surface_name(u)})"
    first += ")"
    out = [first]
    for fname, f in image.get("functions", {}).items():
        surf_fn = _surface_name(fname)
        caps = ",".join(f.get("caps", []))
        header = f"(fn {surf_fn} arity={f['arity']} slots={f['slots']} ret={f.get('return_type','')}"
        if caps:
            header += f" caps={caps}"
        out.append(header)
        for instr in f.get("code", []):
            op = instr[0]
            args = instr[1:]
            # render like bc_instr_digest: "(OP arg0 arg1)"
            # surface callee names for call-like ops
            if op in ("CALL", "CALL_NATIVE", "METHOD", "MODEL_INIT", "STRUCT_NEW") and args:
                surfaced = [_surface_name(str(args[0]))] + [str(x) for x in args[1:]]
                parts = [op] + surfaced
            elif op == "TRAINING_METHOD" and len(args) >= 2:
                surfaced = [_surface_name(str(args[0])), _surface_name(str(args[1]))] + [str(x) for x in args[2:]]
                parts = [op] + surfaced
            elif op == "FIELD_GET" and args:
                surfaced = [_surface_name(str(args[0]))] + [str(x) for x in args[1:]]
                parts = [op] + surfaced
            else:
                normed = []
                for a in args:
                    if a is True:
                        normed.append("true")
                    elif a is False:
                        normed.append("false")
                    elif a is None:
                        normed.append("null")
                    elif a == "None":
                        normed.append("null")
                    elif a == "True":
                        normed.append("true")
                    elif a == "False":
                        normed.append("false")
                    else:
                        normed.append(str(a))
                parts = [op] + normed
            joined = " ".join(p for p in parts)
            out.append(f"  ({joined})")
        out.append(")")
    for sname, fields in image.get("structs", {}).items():
        out.append(f"(struct {_surface_name(sname)} {' '.join(_surface_name(ff) for ff in fields)})")
    return "\n".join(out)


def _emit_bc_module(ir) -> list[str]:
    """Emit PEACOCK probe lines that build BCModule from IR via bytecode.सूत्र APIs."""
    lines: list[str] = []
    mod_name = _surface_name(ir.name) if ir.name else ""
    lines.append(f'    स्थापय mod = new_bc_module({_quote(mod_name)});')
    for use in ir.uses:
        lines.append(f'    bc_module_add_use(mod, {_quote(_surface_name(use))});')
    for sname, fields in ir.structs.items():
        desc = f"(struct {_surface_name(sname)} {' '.join(_surface_name(f) for f in fields)})"
        lines.append(f'    bc_module_add_struct(mod, {_quote(desc)});')
    for fn_name, fn in ir.functions.items():
        bvar = f"b_{fn_name.replace('.','_')}"
        caps = ",".join(sorted(fn.capabilities))
        ret_key = fn.return_type.display() if hasattr(fn.return_type, 'display') else str(fn.return_type)
        # surface ret type
        for k, v in INTERNAL_TO_SOURCE.items():
            ret_key = ret_key.replace(k, v)
        lines.append(f'    स्थापय {bvar} = new_bc_builder({_quote(_surface_name(fn_name))}, {len(fn.decl.params)}, {fn.slot_count}, {_quote(ret_key)}, {_quote(caps)});')
        for instr in fn.instrs:
            op = instr.op
            dest = instr.dest
            args = instr.args
            # map PIR op to bc_on_* calls
            if op == "const":
                v = args[0]
                if isinstance(v, str):
                    vrepr = _quote(v)
                elif isinstance(v, bool):
                    vrepr = _quote("true" if v else "false")
                else:
                    vrepr = _quote(str(v))
                lines.append(f'    bc_on_const({bvar}, {dest}, {vrepr});')
            elif op == "slot_get":
                lines.append(f'    bc_on_slot_get({bvar}, {dest}, {args[0]});')
            elif op == "slot_set":
                lines.append(f'    bc_on_slot_set({bvar}, {args[0]}, {args[1]});')
            elif op == "move":
                lines.append(f'    bc_on_move({bvar}, {dest}, {args[0]});')
            elif op == "binop":
                lines.append(f'    bc_on_binop({bvar}, {dest}, {_quote(args[0])}, {args[1]}, {args[2]});')
            elif op == "unop":
                lines.append(f'    bc_on_unop({bvar}, {dest}, {_quote(args[0])}, {args[1]});')
            elif op == "call":
                callee = _surface_name(args[0]) if args[0] else ""
                regs = list(args[1]) if len(args) > 1 and args[1] else []
                tmp = f"tmp_call_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_call({bvar}, {dest}, {_quote(callee)}, {tmp});')
            elif op == "call_native":
                callee = _surface_name(args[0]) if args[0] else ""
                regs = list(args[1]) if len(args) > 1 and args[1] else []
                tmp = f"tmp_call_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_call_native({bvar}, {dest}, {_quote(callee)}, {tmp});')
            elif op == "method":
                mname = _surface_name(args[0]) if args[0] else ""
                recv = args[1]
                regs = list(args[2]) if len(args) > 2 and args[2] else []
                tmp = f"tmp_m_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_method({bvar}, {dest}, {_quote(mname)}, {recv}, {tmp});')
            elif op == "make_list":
                regs = list(args) if args else []
                tmp = f"tmp_lst_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_make_list({bvar}, {dest}, {tmp});')
            elif op == "make_range":
                lines.append(f'    bc_on_make_range({bvar}, {dest}, {args[0]}, {args[1]});')
            elif op == "index_get":
                lines.append(f'    bc_on_index_get({bvar}, {dest}, {args[0]}, {args[1]});')
            elif op == "index_set":
                lines.append(f'    bc_on_index_set({bvar}, {args[0]}, {args[1]}, {args[2]});')
            elif op == "field_get":
                fname = _surface_name(args[1]) if args[1] else ""
                kind = args[2] if len(args) > 2 else "struct_field"
                lines.append(f'    bc_on_field_get({bvar}, {dest}, {args[0]}, {_quote(fname + "|" + kind)});')
            elif op == "struct_new":
                callee = _surface_name(args[0]) if args[0] else ""
                regs = list(args[1]) if len(args) > 1 and args[1] else []
                tmp = f"tmp_s_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_struct_new({bvar}, {dest}, {_quote(callee)}, {tmp});')
            elif op == "field_set":
                fname = _surface_name(args[1]) if len(args) > 1 else ""
                lines.append(f'    bc_on_field_set({bvar}, {args[0]}, {_quote(fname)}, {args[2]});')
            elif op == "len":
                lines.append(f'    bc_on_len({bvar}, {dest}, {args[0]});')
            elif op == "model_init":
                mname = _surface_name(args[0]) if args[0] else ""
                regs = list(args[1]) if len(args) > 1 and args[1] else []
                tmp = f"tmp_mod_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_model_init({bvar}, {dest}, {_quote(mname)}, {tmp});')
            elif op == "training_method":
                tname = _surface_name(args[0]) if args[0] else ""
                mname = _surface_name(args[1]) if len(args) > 1 else ""
                regs = list(args[2]) if len(args) > 2 and args[2] else []
                tmp = f"tmp_tr_{len(lines)}"
                lines.append(f'    स्थापय {tmp}: सूची<पूर्णाङ्क> = [{",".join(str(x) for x in regs)}];')
                lines.append(f'    bc_on_training_method({bvar}, {dest}, {_quote(tname)}, {_quote(mname)}, {tmp});')
            elif op == "field_get":
                fname = _surface_name(args[1]) if args[1] else ""
                kind = args[2] if len(args) > 2 else "struct_field"
                # encode kind as field|kind
                lines.append(f'    bc_on_field_get({bvar}, {dest}, {args[0]}, {_quote(fname + "|" + kind)});')
                continue
            elif op == "assert":
                if len(args) > 1 and args[1] is not None:
                    lines.append(f'    bc_on_assert({bvar}, {args[0]}, {args[1]});')
                else:
                    lines.append(f'    bc_on_assert({bvar}, {args[0]}, -१);')
            elif op == "jump":
                lines.append(f'    bc_on_jump({bvar}, {_quote(args[0])});')
            elif op == "branch":
                lines.append(f'    bc_on_branch({bvar}, {args[0]}, {_quote(args[1])}, {_quote(args[2])});')
            elif op == "label":
                lines.append(f'    bc_on_label({bvar}, {_quote(args[0])});')
            elif op == "return":
                if args[0] is None:
                    lines.append(f'    bc_on_return({bvar}, -१);')
                else:
                    lines.append(f'    bc_on_return({bvar}, {args[0]});')
            elif op == "throw":
                lines.append(f'    bc_on_throw({bvar}, {args[0]});')
            elif op == "try_begin":
                lines.append(f'    bc_on_try_begin({bvar}, {_quote(args[0])});')
            elif op == "try_end":
                lines.append(f'    bc_on_try_end({bvar});')
            elif op == "catch":
                lines.append(f'    bc_on_catch({bvar}, {dest});')
            elif op == "finally_begin":
                lines.append(f'    bc_on_finally_begin({bvar}, {_quote(args[0])});')
            elif op == "finally_end":
                lines.append(f'    bc_on_finally_end({bvar}, {_quote(args[0])});')
            elif op == "finally_resume":
                lines.append(f'    bc_on_finally_resume({bvar});')
            else:
                lines.append(f'    // skipped bc op {op}')
        # finish function
        fn_var = f"kary_{fn_name.replace('.','_')}"
        lines.append(f'    स्थापय {fn_var} = bc_builder_finish({bvar});')
        lines.append(f'    निश्चिनु(bc_verify_function({fn_var}) == "");')
        lines.append(f'    bc_module_add_function(mod, {fn_var});')
    lines.append('    मुद्रय(bc_module_digest(mod));')
    return lines


class SelfHostBytecodeMismatch(RuntimeError):
    pass


def shadow_bytecode_check(source: str, path: str = "<source>") -> dict:
    from .pipeline import compile_source
    from peacock.runtime.vm import VM
    from peacock.runtime.host import HostPolicy

    compiled = compile_source(source, path, optimize_ir=False)
    if not compiled.ok or compiled.typed is None:
        return {"bytecode_cases": 0, "verified": False}
    ir = build_ir(compiled.typed, source, path)
    image_py = compile_bytecode(ir).image
    py_digest = _bytecode_digest_py(image_py).strip()

    # Build PEACOCK probe
    probe_lines = _emit_bc_module(ir)
    repo_root = Path(__file__).resolve().parents[2]
    lib_path = repo_root / "selfhost" / "bytecode.सूत्र"
    library = lib_path.read_text(encoding="utf-8")
    marker = 'कार्य मुख्य() -> एकक {'
    main_start = library.find(marker)
    if main_start < 0:
        raise SelfHostBytecodeMismatch("bytecode library missing main")
    gen_main = 'कार्य मुख्य() -> एकक {\n' + "\n".join(probe_lines) + "\n}\n"
    combined = library[:main_start] + gen_main
    compiled2 = compile_source(combined, "<selfhost-bc-shadow>", optimize_ir=False)
    if not compiled2.ok:
        raise SelfHostBytecodeMismatch("generated bytecode shadow failed to compile: " + compiled2.diagnostics.render_all(combined))
    out = io.StringIO()
    try:
        VM(compiled2.image, HostPolicy(root=str(repo_root), max_steps=10_000_000), stdout=out).run()
    except Exception as exc:
        raise SelfHostBytecodeMismatch(f"PEACOCK bytecode kernel disagrees: {exc}") from exc
    peacock_digest = out.getvalue().strip()
    if peacock_digest != py_digest:
        raise SelfHostBytecodeMismatch(f"Bytecode digest mismatch:\nPython:\n{py_digest}\n\nPEACOCK:\n{peacock_digest}")
    return {"bytecode_cases": len(image_py.get("functions", {})), "verified": True}
