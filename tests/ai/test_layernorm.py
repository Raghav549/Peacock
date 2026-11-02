import math
import unittest

from peacock.intelligence.tensor import Tensor
from peacock.intelligence.layers import LayerNorm, Dense, Sequential, build_model


class LayerNormTests(unittest.TestCase):
    def test_forward_normalizes(self):
        ln = LayerNorm(4)
        # gamma=1, beta=0 => output should have mean 0 and variance 1
        x = Tensor([1.0, 2.0, 3.0, 4.0], (4,), dtype="Float32")
        y = ln.forward(x)
        # mean should be ~0
        self.assertAlmostEqual(sum(y.tolist()) / 4, 0.0, places=5)
        # variance should be ~1 (with eps)
        mean = sum(y.tolist()) / 4
        var = sum((v - mean) ** 2 for v in y.tolist()) / 4
        self.assertAlmostEqual(var, 1.0, places=4)

    def test_forward_batch(self):
        ln = LayerNorm(3)
        x = Tensor([1.0, 2.0, 3.0, 1.0, 2.0, 3.0], (2, 3), dtype="Float32")
        y = ln.forward(x)
        self.assertEqual(y.shape, (2, 3))
        # Each row should be similarly normalized (tolist returns nested for rank>1)
        tol = y.tolist()
        rows = tol if isinstance(tol[0], list) else [tol[0:3], tol[3:6]]
        for row in rows:
            self.assertAlmostEqual(sum(row) / 3, 0.0, places=5)

    def test_sequential_with_layernorm(self):
        seq = Sequential([Dense(4, 8, "relu", seed=1), LayerNorm(8), Dense(8, 2, seed=1)], input_dim=4)
        x = Tensor([0.5, -0.5, 1.0, -1.0], (4,), dtype="Float32")
        y = seq.forward(x)
        self.assertEqual(y.shape, (2,))
        self.assertEqual(seq.parameter_count(), 4 * 8 + 8 + 8 * 2 + 2 + 8 * 2)  # dense params + layernorm gamma/beta

    def test_build_model_with_layernorm(self):
        m = build_model([4], [2], [{"units": 8, "activation": "relu"}, {"type": "layernorm", "normalized_dim": 8}, {"units": 2}], seed=0)
        self.assertEqual(m.parameter_count, 4 * 8 + 8 + 8 * 2 + 2 + 8 * 2)
        arch = m.architecture()
        self.assertEqual(len(arch["layers"]), 3)
        self.assertEqual(arch["layers"][1]["type"], "layernorm")

    def test_backward_finite_difference(self):
        # Compare autodiff grad to central finite difference
        ln = LayerNorm(4)
        x = Tensor([0.5, -0.3, 1.2, -0.8], (4,), dtype="Float64", requires_grad=True)
        # Forward: y = ln(x), loss = sum(y * y)
        y = ln.forward(x)
        loss = (y * y).sum() if hasattr(y, "sum") else __import__("peacock.intelligence.tensor", fromlist=["sum_all"]).sum_all(y * y)
        from peacock.intelligence.tensor import sum_all

        y = ln.forward(x)
        s = sum_all(y * y)
        s.backward()
        analytic = x.grad.tolist()

        # Finite difference
        eps = 1e-6
        for i in range(4):
            orig = x.data[i]
            x.data[i] = orig + eps
            yp = ln.forward(x)
            lp = sum_all(yp * yp).data[0]
            x.data[i] = orig - eps
            ym = ln.forward(x)
            lm = sum_all(ym * ym).data[0]
            x.data[i] = orig
            numeric = (lp - lm) / (2 * eps)
            self.assertAlmostEqual(analytic[i], numeric, places=4, msg=f"grad mismatch at {i}")

    def test_serialisation(self):
        m = build_model([4], [2], [{"units": 8, "activation": "relu"}, {"type": "layernorm", "normalized_dim": 8}, {"units": 2}], seed=42)
        arch = m.architecture()
        # Round-trip via arch
        from peacock.intelligence.layers import model_from_architecture

        m2 = model_from_architecture(arch, seed=42)
        self.assertEqual(m.parameter_count, m2.parameter_count)
        # Forward should be deterministic with same seed
        x = Tensor([0.1, 0.2, 0.3, 0.4], (4,), dtype="Float32")
        y1 = m.forward(x)
        y2 = m2.forward(x)
        self.assertEqual(y1.tolist(), y2.tolist())


if __name__ == "__main__":
    unittest.main()
