import ctypes
import io
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from peacock.cli import main as cli_main
from peacock.native import NativeBuildError, NativeCodegenError, build_native, build_native_library, generate_c
from peacock.native.builder import runtime_sources
from tests.support import compile_ok, read_example, run_example, run_source


@unittest.skipUnless(shutil.which("cc"), "native AOT tests require a C compiler")
class NativeAOTTests(unittest.TestCase):
    def build(self, source: str, directory: str, name: str = "program", max_steps: int = 2_000_000) -> Path:
        result = compile_ok(source)
        return build_native(result.image, Path(directory) / name, max_steps=max_steps)

    def execute(self, executable: Path) -> subprocess.CompletedProcess:
        return subprocess.run([str(executable)], text=True, capture_output=True, check=False, timeout=10)

    def test_example_matches_reference_vm_and_is_elf(self):
        expected, _outcome, _vm, result = run_example("native.सूत्र")
        with tempfile.TemporaryDirectory() as tmp:
            executable = build_native(result.image, Path(tmp) / "native-demo", keep_c=Path(tmp) / "c")
            completed = self.execute(executable)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, expected)
            self.assertEqual(completed.stderr, "")
            self.assertEqual(executable.read_bytes()[:4], b"\x7fELF")
            generated = (Path(tmp) / "c" / "program.c").read_text()
            self.assertIn("goto L", generated)
            self.assertIn("static PValue p_fn_", generated)
            self.assertNotIn("PUSH_CONST\",", generated)

    def test_cli_native_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "hello-native"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["native", "examples/native.सूत्र", "-o", str(output)])
            self.assertEqual(code, 0)
            self.assertIn("no Python dependency", stdout.getvalue())
            self.assertEqual(self.execute(output).stdout, run_example("native.सूत्र")[0])

    def test_float_unicode_and_string_methods_match(self):
        source = """
        कार्य मुख्य() -> एकक {
            मुद्रय(पाठ्यीकरण(०.१ + ०.२));
            मुद्रय("संस्कृतम्"[२]);
            मुद्रय("संस्कृतम्".उपपाठ्य(२, ५));
            मुद्रय(पाठ्यीकरण("अभिकर्तृ".आरम्भयुक्त("अभि")));
            मुद्रय(पाठ्यीकरण(["अ", "इ", "उ"].संयोजय("-")));
        }
        """
        expected = run_source(source)[0]
        with tempfile.TemporaryDirectory() as tmp:
            completed = self.execute(self.build(source, tmp))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, expected)

    def test_integer_overflow_and_division_by_zero_are_faults(self):
        for expression, code in [("(९२२३३७२०३६८५४७७५८०७ + १)", "PE4004"), ("(१ / ०)", "PE4005")]:
            with self.subTest(expression=expression), tempfile.TemporaryDirectory() as tmp:
                source = f"कार्य मुख्य() -> एकक {{ मुद्रय(पाठ्यीकरण{expression}); }}"
                completed = self.execute(self.build(source, tmp))
                self.assertEqual(completed.returncode, 3)
                self.assertIn(code, completed.stderr)

    def test_native_step_budget(self):
        source = "कार्य मुख्य() -> एकक { यावत् सत्य { स्थापय x = १; } }"
        with tempfile.TemporaryDirectory() as tmp:
            completed = self.execute(self.build(source, tmp, max_steps=25))
            self.assertEqual(completed.returncode, 3)
            self.assertIn("PE4003", completed.stderr)

    def test_unsupported_features_fail_before_native_build(self):
        source = """
        कार्य मुख्य() -> एकक {
            यत्न { क्षिप "no"; } गृह्ण(दोष) { मुद्रय(दोष); }
        }
        """
        with self.assertRaisesRegex(NativeCodegenError, "TRY_BEGIN"):
            generate_c(compile_ok(source).image)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(NativeBuildError, "definitely-missing-cc"):
                build_native(compile_ok("कार्य मुख्य() -> एकक { मुद्रय(\"x\"); }").image, Path(tmp) / "x", compiler="definitely-missing-cc")

    def test_embeddable_library_returns_output_and_faults_to_host(self):
        callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p)

        def invoke(library_path: Path, callback):
            library = ctypes.CDLL(str(library_path))
            library.peacock_run.argtypes = [ctypes.c_int64, callback_type, ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
            library.peacock_run.restype = ctypes.c_int
            library.p_runtime_allocation_count.argtypes = []
            library.p_runtime_allocation_count.restype = ctypes.c_size_t
            error = ctypes.c_char_p()
            status = library.peacock_run(2_000_000, callback, None, ctypes.byref(error))
            allocations = library.p_runtime_allocation_count()
            return status, None if error.value is None else error.value.decode("utf-8"), allocations

        expected = run_example("native.सूत्र")[0]
        with tempfile.TemporaryDirectory() as tmp:
            library_path = build_native_library(
                compile_ok(read_example("native.सूत्र")).image,
                Path(tmp) / "libpeacock.so", keep_c=Path(tmp) / "c",
            )
            chunks = []
            callback = callback_type(lambda data, length, _user: (chunks.append(ctypes.string_at(data, length)) or 0))
            status, error, allocations = invoke(library_path, callback)
            self.assertEqual((status, error, allocations), (0, None, 0))
            self.assertEqual(b"".join(chunks).decode("utf-8"), expected)
            self.assertIn("peacock_run", (Path(tmp) / "c" / "program.h").read_text())

            failing_callback = callback_type(lambda _data, _length, _user: 1)
            status, error, allocations = invoke(library_path, failing_callback)
            self.assertEqual(status, 3)
            self.assertIn("PE5002", error)
            self.assertEqual(allocations, 0)

            fault_path = build_native_library(
                compile_ok('कार्य मुख्य() -> एकक { निश्चिनु असत्य, "दोषः"; }').image,
                Path(tmp) / "libfault.so",
            )
            quiet_callback = callback_type(lambda _data, _length, _user: 0)
            status, error, allocations = invoke(fault_path, quiet_callback)
            self.assertEqual(status, 3)
            self.assertEqual(error, "PE4010: दोषः")
            self.assertEqual(allocations, 0)

    def test_runtime_is_package_data_and_generated_c_is_deterministic(self):
        header, runtime = runtime_sources()
        self.assertIn("PEACOCK_NATIVE_RUNTIME_H", header)
        self.assertIn("p_binary", runtime)
        image = compile_ok(read_example("native.सूत्र")).image
        self.assertEqual(generate_c(image), generate_c(image))


if __name__ == "__main__":
    unittest.main()
