"""Deterministic fuzzers for the lexer, parser, artifact format and model format.

Each fuzzer is seeded and reproducible. A crash is any *unexpected* exception
escaping a component; expected, structured errors are counted as handled.
"""

from __future__ import annotations

import json
import random
import struct
from dataclasses import dataclass, field

from peacock.compiler.lexer import lex
from peacock.compiler.parser import parse
from peacock.intelligence.random import RNG
from peacock.intelligence.serialization import model_from_bytes
from peacock.runtime.artifact import ArtifactFormatError, image_from_bytes

_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    "{}()[]<>.,;:+-*/%**=!&|?\"'\\ \n\t"
    "模块模型训练函数张量颜色图案节点量子"
)


@dataclass
class FuzzReport:
    target: str
    iterations: int
    seed: int
    handled: int = 0
    crashes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.crashes

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "iterations": self.iterations,
            "seed": self.seed,
            "handled": self.handled,
            "crashes": list(self.crashes),
            "ok": self.ok,
        }


def _random_source(rng: random.Random, max_length: int = 220) -> str:
    length = rng.randint(0, max_length)
    return "".join(rng.choice(_ALPHABET) for _ in range(length))


def fuzz_lexer(iterations: int = 300, seed: int = 1) -> FuzzReport:
    report = FuzzReport("lexer", iterations, seed)
    rng = random.Random(seed)
    for i in range(iterations):
        source = _random_source(rng)
        try:
            tokens, diag = lex(source)
            if not tokens or tokens[-1].kind.name != "EOF":
                report.crashes.append(f"iteration {i}: missing EOF token")
                continue
            for token in tokens:
                if token.span.start > token.span.end:
                    report.crashes.append(f"iteration {i}: inverted span")
                    break
                if token.span.end > len(source):
                    report.crashes.append(f"iteration {i}: span beyond source")
                    break
            else:
                report.handled += 1
        except Exception as exc:  # noqa: BLE001 - fuzzing must catch everything
            report.crashes.append(f"iteration {i}: {type(exc).__name__}: {exc}")
    return report


def fuzz_parser(iterations: int = 300, seed: int = 2) -> FuzzReport:
    report = FuzzReport("parser", iterations, seed)
    rng = random.Random(seed)
    for i in range(iterations):
        source = _random_source(rng, max_length=400)
        try:
            tokens, lex_diag = lex(source)
            if lex_diag.has_errors:
                report.handled += 1
                continue
            module, diag = parse(tokens, source)
            if module is None:
                report.crashes.append(f"iteration {i}: parser returned no module")
                continue
            report.handled += 1
        except Exception as exc:  # noqa: BLE001
            report.crashes.append(f"iteration {i}: {type(exc).__name__}: {exc} | {source!r}")
    return report


def fuzz_artifact(iterations: int = 300, seed: int = 3, valid_artifact: bytes | None = None) -> FuzzReport:
    from peacock.compiler.pipeline import compile_source
    from peacock.runtime.artifact import image_to_bytes

    report = FuzzReport("artifact", iterations, seed)
    if valid_artifact is None:
        result = compile_source('प्रकरण fuzz\nकार्य मुख्य() -> एकक { मुद्रय("ok"); }', "fuzz.सूत्र")
        if not result.ok:
            report.crashes.append("could not build seed artifact")
            return report
        valid_artifact = image_to_bytes(result.image)
    rng = random.Random(seed)
    for i in range(iterations):
        data = bytearray(valid_artifact)
        mode = rng.randrange(4)
        if mode == 0 and data:
            for _ in range(rng.randint(1, 6)):
                data[rng.randrange(len(data))] = rng.randrange(256)
        elif mode == 1:
            data = data[: rng.randrange(len(data) + 1)]
        elif mode == 2:
            data.extend(bytes(rng.randrange(256) for _ in range(rng.randint(1, 32))))
        else:
            start = rng.randrange(max(1, len(data)))
            data = data[:start] + bytes(rng.randrange(256) for _ in range(rng.randint(1, 8))) + data[start:]
        try:
            image = image_from_bytes(bytes(data))
            if not isinstance(image, dict):
                report.crashes.append(f"iteration {i}: non-dict image accepted")
            else:
                report.handled += 1
        except (ArtifactFormatError, ValueError, struct.error, UnicodeDecodeError, json.JSONDecodeError):
            report.handled += 1
        except Exception as exc:  # noqa: BLE001
            report.crashes.append(f"iteration {i}: {type(exc).__name__}: {exc}")
    return report


def fuzz_model(iterations: int = 200, seed: int = 4) -> FuzzReport:
    from peacock.intelligence.layers import build_model
    from peacock.intelligence.serialization import model_to_bytes

    report = FuzzReport("model", iterations, seed)
    model = build_model((2,), (2,), [(4, "relu"), (2, "linear")], seed=1)
    valid = model_to_bytes(model)
    rng = random.Random(seed)
    for i in range(iterations):
        data = bytearray(valid)
        mode = rng.randrange(4)
        if mode == 0 and data:
            for _ in range(rng.randint(1, 5)):
                data[rng.randrange(len(data))] = rng.randrange(256)
        elif mode == 1:
            data = data[: rng.randrange(len(data) + 1)]
        elif mode == 2:
            data.extend(bytes(rng.randrange(256) for _ in range(rng.randint(1, 24))))
        else:
            start = rng.randrange(max(1, len(data)))
            data = data[:start] + bytes(rng.randrange(256) for _ in range(rng.randint(1, 6))) + data[start:]
        try:
            model_from_bytes(bytes(data))
            report.handled += 1
        except (ValueError, struct.error, UnicodeDecodeError, json.JSONDecodeError):
            report.handled += 1
        except Exception as exc:  # noqa: BLE001
            report.crashes.append(f"iteration {i}: {type(exc).__name__}: {exc}")
    return report


def run_all(iterations: int = 300, seed: int = 1) -> list[FuzzReport]:
    return [
        fuzz_lexer(iterations, seed),
        fuzz_parser(iterations, seed + 1),
        fuzz_artifact(iterations, seed + 2),
        fuzz_model(max(50, iterations * 2 // 3), seed + 3),
    ]
