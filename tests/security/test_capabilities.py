import io
import os
import tempfile
import unittest
from pathlib import Path

from peacock.compiler.diagnostics import CapabilityError, HostError, ResourceLimitError
from peacock.compiler.pipeline import compile_source
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM
from tests.support import REPO_ROOT, compile_ok, expect_diagnostic


def vm_for(source, grants=(), root=None, **kwargs):
    result = compile_ok(source)
    policy = HostPolicy(grants=frozenset(grants), root=str(root or REPO_ROOT), **kwargs)
    return VM(result.image, policy, stdout=io.StringIO())


class StaticCapabilityTests(unittest.TestCase):
    def test_fs_requires_capability_declaration(self):
        expect_diagnostic(
            'use fs\nfn main() -> Unit { let x = fs.read_text("a.txt"); }',
            "PE3005",
            "fs",
        )

    def test_create_dir_requires_capability_declaration(self):
        expect_diagnostic(
            'use fs\nfn main() -> Unit { fs.create_dir("cache/nested"); }',
            "PE3005",
            "fs",
        )

    def test_compute_requires_capability_declaration(self):
        expect_diagnostic(
            "use nn\nfn main() -> Unit { let w = nn.parameter([1.0]); }",
            "PE3005",
            "compute",
        )

    def test_capability_does_not_escape_nested_functions(self):
        source = """
        use fs
        fn helper() -> String { return fs.read_text("a.txt"); }
        fn main() -> Unit { capability fs; let text = helper(); }
        """
        expect_diagnostic(source, "PE3005", "fs")

    def test_capability_must_be_first_and_direct(self):
        expect_diagnostic(
            'use fs\nfn main() -> Unit { if true { capability fs; } }',
            "PE3005",
            "function body",
        )

    def test_unknown_capability_is_a_compile_error(self):
        expect_diagnostic(
            "fn main() -> Unit { capability root; }", "PE3005", "unknown capability"
        )

    def test_capability_duplicate(self):
        expect_diagnostic(
            "fn main() -> Unit { capability fs; capability fs; }", "PE3005", "twice"
        )


class RuntimeCapabilityTests(unittest.TestCase):
    def test_declared_but_not_granted(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            fs.write_text("x.txt", "data");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm = vm_for(source, grants=(), root=tmp)
            with self.assertRaises(CapabilityError):
                vm.run()
            self.assertFalse((Path(tmp) / "x.txt").exists())

    def test_granted_without_declaration_cannot_compile(self):
        source = 'use fs\nfn main() -> Unit { fs.write_text("x.txt", "data"); }'
        result = compile_source(source, "x.pac")
        self.assertFalse(result.ok)
        self.assertTrue(any(d.code == "PE3005" for d in result.diagnostics))

    def test_grant_does_not_leak_between_vms(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            fs.write_text("x.txt", "data");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm_for(source, grants=("fs",), root=tmp).run()
            self.assertTrue((Path(tmp) / "x.txt").exists())
            other = Path(tmp) / "other"
            other.mkdir()
            vm = vm_for(source, grants=(), root=other)
            with self.assertRaises(CapabilityError):
                vm.run()
            self.assertFalse((other / "x.txt").exists())

    def test_create_dir_is_grant_gated_and_creates_nested_paths(self):
        source = '''\
use fs
fn main() -> Unit {
    capability fs;
    fs.create_dir("generated/pages/nested");
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            denied = vm_for(source, grants=(), root=tmp)
            with self.assertRaises(CapabilityError):
                denied.run()
            self.assertFalse((Path(tmp) / "generated").exists())
            vm_for(source, grants=("fs",), root=tmp).run()
            self.assertTrue((Path(tmp) / "generated/pages/nested").is_dir())

    def test_ui_grant_does_not_grant_filesystem_access(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            let text = fs.read_text("secret.txt");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "secret.txt").write_text("secret", encoding="utf-8")
            vm = vm_for(source, grants=("ui",), root=tmp)
            with self.assertRaises(CapabilityError) as ctx:
                vm.run()
            self.assertIn("fs", str(ctx.exception))
            self.assertNotIn("fs", vm.host.grants)

    def test_fs_grant_does_not_grant_presentation(self):
        source = """
        use graphics
        fn main() -> Unit {
            capability ui;
            let canvas = graphics.canvas(8, 8);
            graphics.present(canvas);
        }
        """
        presented = []
        with tempfile.TemporaryDirectory() as tmp:
            vm = vm_for(
                source,
                grants=("fs",),
                root=tmp,
                presenter=lambda canvas: presented.append(canvas),
            )
            with self.assertRaises(CapabilityError) as ctx:
                vm.run()
            self.assertIn("ui", str(ctx.exception))
        self.assertEqual(presented, [])

    def test_present_requires_ui_declaration(self):
        expect_diagnostic(
            'use graphics\nfn main() -> Unit { let c = graphics.canvas(4, 4); graphics.present(c); }',
            "PE3005",
            "ui",
        )

    def test_unknown_host_grant_rejected(self):
        with self.assertRaises(HostError):
            HostPolicy(grants=frozenset({"camera"}))

    def test_capability_denial_is_catchable_but_grants_nothing(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            try { let text = fs.read_text("secret.txt"); print(text); }
            catch (error) { print("denied: " + error); }
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "secret.txt").write_text("secret", encoding="utf-8")
            result = compile_ok(source)
            out = io.StringIO()
            vm = VM(result.image, HostPolicy(grants=frozenset(), root=tmp), stdout=out)
            vm.run()
            self.assertIn("denied:", out.getvalue())
            self.assertNotIn("secret", out.getvalue())

    def test_panic_cannot_be_caught(self):
        from peacock.compiler.diagnostics import PanicError

        source = 'fn main() -> Unit { try { panic("fatal"); } catch (e) { print("swallowed"); } }'
        result = compile_ok(source)
        vm = VM(result.image, HostPolicy(), stdout=io.StringIO())
        with self.assertRaises(PanicError):
            vm.run()


class SandboxTests(unittest.TestCase):
    def test_parent_traversal(self):
        source = 'use fs\nfn main() -> Unit { capability fs; let x = fs.read_text("../secret.txt"); }'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (Path(tmp) / "secret.txt").write_text("secret", encoding="utf-8")
            vm = vm_for(source, grants=("fs",), root=root)
            with self.assertRaises(HostError) as ctx:
                vm.run()
            self.assertIn("escapes", str(ctx.exception))

    def test_nested_traversal(self):
        source = 'use fs\nfn main() -> Unit { capability fs; let x = fs.read_text("a/../../secret.txt"); }'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            vm = vm_for(source, grants=("fs",), root=root)
            with self.assertRaises(HostError):
                vm.run()

    def test_create_dir_cannot_escape_sandbox(self):
        source = 'use fs\nfn main() -> Unit { capability fs; fs.create_dir("../outside/new"); }'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            vm = vm_for(source, grants=("fs",), root=root)
            with self.assertRaises(HostError) as ctx:
                vm.run()
            self.assertIn("escapes", str(ctx.exception))
            self.assertFalse((Path(tmp) / "outside").exists())

    def test_absolute_path(self):
        source = 'use fs\nfn main() -> Unit { capability fs; let x = fs.read_text("/etc/passwd"); }'
        with tempfile.TemporaryDirectory() as tmp:
            vm = vm_for(source, grants=("fs",), root=tmp)
            with self.assertRaises(HostError):
                vm.run()

    def test_windows_style_absolute_path(self):
        source = 'use fs\nfn main() -> Unit { capability fs; let x = fs.read_text("C:\\\\Windows\\\\win.ini"); }'
        with tempfile.TemporaryDirectory() as tmp:
            vm = vm_for(source, grants=("fs",), root=tmp)
            with self.assertRaises(HostError):
                vm.run()

    def test_symlink_escape(self):
        source = 'use fs\nfn main() -> Unit { capability fs; let x = fs.read_text("link.txt"); }'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            target = Path(tmp) / "secret.txt"
            target.write_text("secret", encoding="utf-8")
            try:
                os.symlink(target, root / "link.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported")
            vm = vm_for(source, grants=("fs",), root=root)
            with self.assertRaises(HostError):
                vm.run()

    def test_nul_byte(self):
        policy = HostPolicy(root=str(REPO_ROOT))
        with self.assertRaises(HostError):
            policy.resolve_path("bad\x00name")

    def test_file_size_limit(self):
        source = 'use fs\nfn main() -> Unit { capability fs; fs.write_text("big.txt", "0123456789"); }'
        with tempfile.TemporaryDirectory() as tmp:
            vm = vm_for(source, grants=("fs",), root=tmp, max_file_bytes=4)
            with self.assertRaises(HostError):
                vm.run()

    def test_sandbox_root_cannot_be_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(HostError):
                HostPolicy(root=str(path))


class ResourceLimitTests(unittest.TestCase):
    def test_step_limit(self):
        vm = vm_for("fn main() -> Unit { while true { } }", max_steps=1000)
        with self.assertRaises(ResourceLimitError) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4003")

    def test_call_depth_limit(self):
        source = "fn recurse(n: Int) -> Int { return recurse(n + 1); }\nfn main() -> Unit { let x = recurse(0); }"
        vm = vm_for(source, max_call_depth=32)
        with self.assertRaises(ResourceLimitError):
            vm.run()

    def test_output_limit(self):
        source = 'fn main() -> Unit { while true { print("aaaaaaaa"); } }'
        vm = vm_for(source, max_output_chars=32, max_steps=100000)
        with self.assertRaises(ResourceLimitError):
            vm.run()

    def test_tensor_element_limit(self):
        source = """
        use nn
        fn main() -> Unit {
            capability compute;
            let w = nn.parameter([[0.0, 0.0], [0.0, 0.0]]);
        }
        """
        vm = vm_for(source, grants=("compute",), max_tensor_elements=2)
        with self.assertRaises(ResourceLimitError):
            vm.run()

    def test_dataset_sample_limit(self):
        source = """
        use nn
        fn main() -> Unit {
            capability compute;
            let d = nn.spiral(10, 0.1, 1);
        }
        """
        vm = vm_for(source, grants=("compute",), max_dataset_samples=5)
        with self.assertRaises(ResourceLimitError):
            vm.run()

    def test_training_epoch_limit(self):
        source = """
        use nn
        fn main() -> Unit {
            capability compute;
            let net = Legacy.init(seed: 1);
            let data = nn.xor();
            let losses = LegacyTraining.run(net, data);
        }
        model Legacy {
            input x: Tensor<Float32, [2]>
            output y: Tensor<Float32, [2]>
            stack { Dense(units: 4, activation: relu) Dense(units: 2) }
        }
        training LegacyTraining { epochs: 5 }
        """
        vm = vm_for(source, grants=("compute",), max_training_epochs=2)
        with self.assertRaises(ResourceLimitError):
            vm.run()

    def test_limits_are_not_shared_between_runs(self):
        source = 'fn main() -> Unit { print("ok"); }'
        vm = vm_for(source, max_steps=20)
        vm.run()
        vm.run()  # a fresh execution resets the step budget


class NoHostEscapeTests(unittest.TestCase):
    def test_strings_are_not_code(self):
        source = 'fn main() -> Unit { let code = "sys.exit(1)"; print(code); }'
        result = compile_ok(source)
        out = io.StringIO()
        VM(result.image, HostPolicy(), stdout=out).run()
        self.assertEqual(out.getvalue().strip(), "sys.exit(1)")

    def test_unknown_native_is_not_dispatchable(self):
        result = compile_ok('fn main() -> Unit { print("x"); }')
        image = result.image
        image = {**image, "functions": {**image["functions"]}}
        code = [["CALL_NATIVE", "os.system", 0], ["RET", 0]]
        image["functions"]["main"] = {
            **image["functions"]["main"],
            "code": code,
            "lines": [[1, 1], [1, 1]],
            "slots": 1,
        }
        from peacock.compiler.bytecode import BytecodeError
        from peacock.runtime.artifact import ArtifactFormatError

        with self.assertRaises((BytecodeError, ArtifactFormatError)):
            VM(image, HostPolicy())

    def test_verifier_rejects_unknown_capability_in_image(self):
        result = compile_ok('fn main() -> Unit { print("x"); }')
        image = {**result.image, "functions": {**result.image["functions"]}}
        image["functions"]["main"] = {**image["functions"]["main"], "caps": ["root"]}
        from peacock.compiler.bytecode import BytecodeError
        from peacock.runtime.artifact import ArtifactFormatError

        with self.assertRaises((BytecodeError, ArtifactFormatError)):
            VM(image, HostPolicy())

    def test_artifact_hash_prevents_patch(self):
        from peacock.runtime.artifact import ArtifactFormatError, image_to_bytes, image_from_bytes

        result = compile_ok('fn main() -> Unit { print("x"); }')
        blob = bytearray(image_to_bytes(result.image))
        blob[-1] ^= 0x01
        with self.assertRaises(ArtifactFormatError):
            image_from_bytes(bytes(blob))


if __name__ == "__main__":
    unittest.main()
