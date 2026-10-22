"""Build standalone native executables from generated PEACOCK C source."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
import shutil
import subprocess
import tempfile

from .codegen import NativeCodegenError, generate_c


class NativeBuildError(RuntimeError):
    pass


def runtime_sources() -> tuple[str, str]:
    root = resources.files("peacock.native")
    return (
        root.joinpath("runtime.h").read_text(encoding="utf-8"),
        root.joinpath("runtime.c").read_text(encoding="utf-8"),
    )


def build_native(
    image: dict,
    output: str | Path,
    *,
    compiler: str = "cc",
    keep_c: str | Path | None = None,
    max_steps: int = 2_000_000,
) -> Path:
    """Compile a verified image to an executable with no Python dependency.

    The executable links only the generated program, PEACOCK's C runtime and the
    platform C/math libraries.  ``keep_c`` optionally retains the exact generated
    translation unit and runtime for audit/reproducibility.
    """

    if max_steps < 1:
        raise NativeBuildError("native max-steps must be positive")
    source = generate_c(image).replace(
        "p_runtime_init(2000000);", f"p_runtime_init({int(max_steps)});", 1
    )
    executable = shutil.which(compiler)
    if executable is None:
        raise NativeBuildError(
            f"C compiler {compiler!r} was not found; install a C11 compiler or pass --cc"
        )
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    header, runtime = runtime_sources()
    with tempfile.TemporaryDirectory(prefix="peacock-native-") as temporary:
        build = Path(temporary)
        (build / "program.c").write_text(source, encoding="utf-8")
        (build / "runtime.h").write_text(header, encoding="utf-8")
        (build / "runtime.c").write_text(runtime, encoding="utf-8")
        command = [
            executable, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-ffile-prefix-map=" + str(build) + "=.",
            str(build / "program.c"), str(build / "runtime.c"), "-lm", "-o", str(destination),
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode:
            raise NativeBuildError(
                "native C compilation failed:\n" + (result.stderr or result.stdout).strip()
            )
        if keep_c is not None:
            kept = Path(keep_c)
            kept.mkdir(parents=True, exist_ok=True)
            (kept / "program.c").write_text(source, encoding="utf-8")
            (kept / "runtime.h").write_text(header, encoding="utf-8")
            (kept / "runtime.c").write_text(runtime, encoding="utf-8")
    return destination


def build_native_library(
    image: dict,
    output: str | Path,
    *,
    compiler: str = "cc",
    keep_c: str | Path | None = None,
) -> Path:
    """Build the supported subset as a C shared library for native host shells."""

    source = generate_c(image, library=True)
    executable = shutil.which(compiler)
    if executable is None:
        raise NativeBuildError(f"C compiler {compiler!r} was not found; install a C11 compiler or pass --cc")
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    header, runtime = runtime_sources()
    program_header = (
        "#ifndef PEACOCK_GENERATED_PROGRAM_H\n#define PEACOCK_GENERATED_PROGRAM_H\n"
        "#include \"runtime.h\"\n"
        "int peacock_run(int64_t max_steps, POutputCallback output, void *userdata, const char **error_message);\n"
        "#endif\n"
    )
    with tempfile.TemporaryDirectory(prefix="peacock-native-library-") as temporary:
        build = Path(temporary)
        for name, content in (("program.c", source), ("program.h", program_header), ("runtime.h", header), ("runtime.c", runtime)):
            (build / name).write_text(content, encoding="utf-8")
        command = [
            executable, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
            "-ffile-prefix-map=" + str(build) + "=.",
            str(build / "program.c"), str(build / "runtime.c"), "-lm", "-o", str(destination),
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode:
            raise NativeBuildError("native C library compilation failed:\n" + (result.stderr or result.stdout).strip())
        if keep_c is not None:
            kept = Path(keep_c)
            kept.mkdir(parents=True, exist_ok=True)
            for name, content in (("program.c", source), ("program.h", program_header), ("runtime.h", header), ("runtime.c", runtime)):
                (kept / name).write_text(content, encoding="utf-8")
    return destination


__all__ = ["NativeBuildError", "NativeCodegenError", "build_native", "build_native_library", "generate_c"]
