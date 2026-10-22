"""Human-readable disassembly of PEACOCK bytecode images.

Opcode names are the stable bytecode instruction set. Source-level identifiers,
types, capabilities, layer activations, and training options are rendered in the
canonical Sanskrit surface vocabulary.
"""

from __future__ import annotations

from peacock.sanskrit import surface, surface_enum, surface_type


def _label_targets(image: dict) -> dict[tuple[str, int], str]:
    labels: dict[tuple[str, int], str] = {}
    for name, fn in image["functions"].items():
        for ip, instr in enumerate(fn["code"]):
            if instr[0] in ("JUMP", "JUMP_IF_FALSE"):
                target = instr[1]
                labels.setdefault((name, target), f"L_{target}")
            elif instr[0] == "TRY_BEGIN":
                labels.setdefault((name, instr[1]), f"CATCH_{instr[1]}")
    return labels


def _source_argument(opcode: str, index: int, arg):
    """Translate only operands known to be source identifiers, never user text."""

    if index == 1 and opcode in {
        "CALL", "CALL_NATIVE", "METHOD", "MODEL_INIT", "STRUCT_NEW",
        "FIELD_GET", "FIELD_SET", "TRAINING_METHOD",
    }:
        return surface(arg)
    if index == 2 and opcode == "TRAINING_METHOD":
        return surface(arg)
    return arg


def disassemble(image: dict) -> str:
    labels = _label_targets(image)
    lines: list[str] = []
    lines.append(f"; PEACOCK bytecode {image.get('language_version')} module={surface(image.get('module', ''))!r}")
    lines.append(f"; source={image.get('source_path')} sha256={image.get('source_sha256', '')[:16]}...")
    order = sorted(image["functions"], key=lambda n: (n != "main", n))
    for name in order:
        fn = image["functions"][name]
        params = ", ".join(surface(param) for param in fn.get("params", []))
        caps = ", ".join(surface(capability) for capability in fn["caps"]) or "none"
        lines.append("")
        lines.append(
            f"function {surface(name)}({params}) -> "
            f"{surface_type(fn.get('return_type', 'Unit'))}"
        )
        lines.append(f"  slots={fn['slots']} capabilities={caps}")
        for ip, instr in enumerate(fn["code"]):
            if (name, ip) in labels:
                lines.append(f"{labels[(name, ip)]}:")
            line, column = fn["lines"][ip]
            args = []
            for index, arg in enumerate(instr[1:], start=1):
                if instr[0] in ("JUMP", "JUMP_IF_FALSE") and index == 1:
                    args.append(labels.get((name, arg), str(arg)))
                elif instr[0] == "TRY_BEGIN" and index == 1:
                    args.append(labels.get((name, arg), str(arg)))
                else:
                    args.append(repr(_source_argument(instr[0], index, arg)))
            rendered = instr[0]
            if args:
                rendered += " " + ", ".join(args)
            lines.append(f"  {ip:5d}  {line:>4}:{column:<3} {rendered}")
    lines.append("")
    models = image.get("models", {})
    if models:
        lines.append("models:")
        for name, spec in sorted(models.items()):
            layers = " -> ".join(
                f"{surface('Dense')}({units},{surface_enum(activation)})"
                for units, activation in spec["layers"]
            )
            lines.append(
                f"  {surface(name)}: [{surface_type(spec['input_dtype'])}{spec['input_shape']}] -> "
                f"[{surface_type(spec['output_dtype'])}{spec['output_shape']}] {layers}"
            )
    trainings = image.get("trainings", {})
    if trainings:
        lines.append("training declarations:")
        for name, config in sorted(trainings.items()):
            options = ", ".join(
                f"{surface(key)}={surface_enum(value) if isinstance(value, str) else value!r}"
                for key, value in sorted(config.items())
            )
            lines.append(f"  {surface(name)}: {options}")
    if image.get("uses"):
        lines.append(f"uses: {', '.join(surface(use) for use in image['uses'])}")
    return "\n".join(lines)
