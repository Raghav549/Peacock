import unittest

from peacock.compiler.diagnostics import CapabilityError
from peacock.intelligence.gpu import GPUError, backend_names, create_backend
from peacock.intelligence.tensor import Tensor
from peacock.runtime.errors import VMFault
from tests.support import run_source


class ComputeBackendTests(unittest.TestCase):
    def setUp(self):
        self.a = Tensor([1, 2, 3, 4], (2, 2))
        self.b = Tensor([5, 6, 7, 8], (2, 2))

    def assertTensorAlmostEqual(self, actual, expected):
        self.assertEqual(actual.shape, expected.shape)
        for left, right in zip(actual.data, expected.data):
            self.assertAlmostEqual(left, right, places=5)

    def test_cpu_reference_operations_and_info(self):
        backend = create_backend("cpu")
        try:
            self.assertEqual(backend.add(self.a, self.b).data, [6.0, 8.0, 10.0, 12.0])
            self.assertEqual(backend.multiply(self.a, self.b).data, [5.0, 12.0, 21.0, 32.0])
            self.assertEqual(backend.relu(Tensor([-2, 0, 3], (3,))).data, [0.0, 0.0, 3.0])
            self.assertEqual(backend.matmul(self.a, self.b).data, [19.0, 22.0, 43.0, 50.0])
            self.assertFalse(backend.info.hardware)
            self.assertIn("hardware=no", backend.info.lines())
        finally:
            backend.close()

    def test_non_square_matmul_uses_inner_dimensions_not_elementwise_shapes(self):
        backend = create_backend("cpu")
        left = Tensor([1, 2, 3, 4, 5, 6], (2, 3))
        right = Tensor([7, 8, 9, 10, 11, 12], (3, 2))
        result = backend.matmul(left, right)
        self.assertEqual(result.shape, (2, 2))
        self.assertEqual(result.data, [58.0, 64.0, 139.0, 154.0])
        with self.assertRaisesRegex(GPUError, r"\[m,k\]"):
            backend.matmul(left, left)

    def test_invalid_backends_shapes_and_empty_tensors(self):
        with self.assertRaisesRegex(GPUError, "unknown compute backend"):
            create_backend("invalid")
        backend = create_backend("cpu")
        with self.assertRaisesRegex(GPUError, "equal shapes"):
            backend.add(Tensor([1], (1,)), Tensor([1, 2], (2,)))
        with self.assertRaisesRegex(GPUError, "nonempty"):
            backend.relu(Tensor([], (0,)))
        if "opencl" not in backend_names():
            with self.assertRaisesRegex(GPUError, "no OpenCL"):
                create_backend("opencl")

    @unittest.skipUnless("opencl" in backend_names(), "no OpenCL hardware/driver in this environment")
    def test_real_opencl_matches_cpu(self):
        cpu, gpu = create_backend("cpu"), create_backend("opencl")
        try:
            self.assertTrue(gpu.info.hardware)
            for operation in ("add", "multiply", "matmul"):
                with self.subTest(operation=operation):
                    self.assertTensorAlmostEqual(
                        getattr(gpu, operation)(self.a, self.b),
                        getattr(cpu, operation)(self.a, self.b),
                    )
            self.assertTensorAlmostEqual(gpu.relu(self.a), cpu.relu(self.a))
            left = Tensor([1, 2, 3, 4, 5, 6], (2, 3))
            right = Tensor([7, 8, 9, 10, 11, 12], (3, 2))
            self.assertTensorAlmostEqual(gpu.matmul(left, right), cpu.matmul(left, right))
        finally:
            gpu.close()
            cpu.close()


class NativeComputeTests(unittest.TestCase):
    SOURCE = """
    उपयोग गणनयन्त्र
    कार्य मुख्य() -> एकक {
        अधिकार गणना;
        स्थापय अ = आयामीकरण([[१.०, २.०], [३.०, ४.०]]);
        स्थापय ब = आयामीकरण([[५.०, ६.०], [७.०, ८.०]]);
        स्थापय योग = गणनयन्त्र.संकलय("क्रमक", अ, ब);
        स्थापय गुणन = गणनयन्त्र.आव्यूहगुणन("क्रमक", अ, ब);
        मुद्रय(पाठ्यीकरण(योग));
        मुद्रय(पाठ्यीकरण(गुणन));
        निश्चिनु गणनयन्त्र.पश्चात्तन्त्राणि()[०] == "क्रमक";
        मुद्रय(गणनयन्त्र.विवरण("क्रमक")[०]);
        मुद्रय(गणनयन्त्र.विवरण("क्रमक")[४]);
    }
    """

    def test_native_cpu_backend_and_sanskrit_introspection(self):
        result = run_source(self.SOURCE, grants=("compute",))
        self.assertIn("[[6.0, 8.0], [10.0, 12.0]]", result[0])
        self.assertIn("[[19.0, 22.0], [43.0, 50.0]]", result[0])
        self.assertIn("पश्चात्तन्त्र=क्रमक", result[0])
        self.assertIn("भौतिक=असत्य", result[0])

    def test_compute_grant_is_required(self):
        with self.assertRaises(CapabilityError):
            run_source(self.SOURCE)

    @unittest.skipIf("opencl" in backend_names(), "device-unavailable diagnostic is environment-specific")
    def test_explicit_accelerator_never_silently_falls_back(self):
        source = """
        उपयोग गणनयन्त्र
        कार्य मुख्य() -> एकक {
            अधिकार गणना;
            स्थापय अ = आयामीकरण([१.०]);
            स्थापय ब = गणनयन्त्र.धनाङ्क("त्वरक", अ);
        }
        """
        with self.assertRaises(VMFault) as caught:
            run_source(source, grants=("compute",))
        self.assertEqual(caught.exception.code, "PE6002")
        self.assertIn("OpenCL", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
