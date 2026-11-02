import math
import unittest

from peacock.intelligence.tensor import Tensor, matmul, scaled_dot_product_attention, sum_all
from peacock.intelligence.layers import (
    MultiHeadAttention,
    TransformerBlock,
    positional_encoding,
    build_model,
)


class BatchedMatmulTests(unittest.TestCase):
    def test_2d_still_works(self):
        a = Tensor([1, 2, 3, 4], (2, 2), dtype="Float32")
        b = Tensor([5, 6, 7, 8], (2, 2), dtype="Float32")
        c = matmul(a, b)
        self.assertEqual(c.shape, (2, 2))
        self.assertEqual(c.tolist(), [[19, 22], [43, 50]])

    def test_3d_batched(self):
        a = Tensor([1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4], (2, 2, 3), dtype="Float32")
        b = Tensor([1, 0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1], (2, 3, 2), dtype="Float32")
        c = matmul(a, b)
        self.assertEqual(c.shape, (2, 2, 2))
        # first batch: [[1,2,3],[4,5,6]] @ [[1,0],[0,1],[1,1]] = [[4,5],[10,11]]
        self.assertEqual(c.tolist()[0][0], [4, 5])
        self.assertEqual(c.tolist()[0][1], [10, 11])

    def test_4d_batched(self):
        a = Tensor.ones((2, 3, 4, 5), dtype="Float32")
        b = Tensor.ones((2, 3, 5, 6), dtype="Float32")
        c = matmul(a, b)
        self.assertEqual(c.shape, (2, 3, 4, 6))
        # all ones matmul should give 5 everywhere (k=5)
        self.assertEqual(c.tolist()[0][0][0][0], 5)


class AttentionTests(unittest.TestCase):
    def test_scaled_dot_product_basic(self):
        q = Tensor([1, 0, 0, 1], (2, 2), dtype="Float32")
        k = Tensor([1, 0, 0, 1], (2, 2), dtype="Float32")
        v = Tensor([1, 2, 3, 4], (2, 2), dtype="Float32")
        out = scaled_dot_product_attention(q, k, v)
        self.assertEqual(out.shape, (2, 2))
        # QK^T / sqrt2 = [[1,0],[0,1]]/sqrt2 -> softmax -> approx [[0.67,0.33],[0.33,0.67]]
        # output = weights @ V
        self.assertAlmostEqual(out.tolist()[0][0], 1.66, places=1)

    def test_batched_attention(self):
        q = Tensor.randn((2, 3, 4), dtype="Float32", seed=0)
        k = Tensor.randn((2, 3, 4), dtype="Float32", seed=1)
        v = Tensor.randn((2, 3, 4), dtype="Float32", seed=2)
        out = scaled_dot_product_attention(q, k, v)
        self.assertEqual(out.shape, (2, 3, 4))

    def test_attention_backward(self):
        q = Tensor([0.5, 0.2, 0.3, 0.4], (2, 2), dtype="Float64", requires_grad=True)
        k = Tensor([0.1, 0.6, 0.7, 0.2], (2, 2), dtype="Float64", requires_grad=True)
        v = Tensor([1.0, 2.0, 3.0, 4.0], (2, 2), dtype="Float64", requires_grad=True)
        out = scaled_dot_product_attention(q, k, v)
        loss = sum_all(out * out)
        loss.backward()
        self.assertIsNotNone(q.grad)
        self.assertIsNotNone(k.grad)
        self.assertIsNotNone(v.grad)
        # gradients should be non-zero
        self.assertNotEqual(sum(abs(x) for x in q.grad.data), 0)
        self.assertNotEqual(sum(abs(x) for x in k.grad.data), 0)


class MultiHeadAttentionTests(unittest.TestCase):
    def test_forward_shapes(self):
        mha = MultiHeadAttention(input_dim=8, d_model=8, num_heads=2, seed=0)
        x = Tensor.randn((2, 4, 8), dtype="Float32", seed=1)
        y = mha.forward(x)
        self.assertEqual(y.shape, (2, 4, 8))

    def test_2d_input(self):
        mha = MultiHeadAttention(input_dim=4, d_model=4, num_heads=2, seed=0)
        x = Tensor.randn((3, 4), dtype="Float32", seed=1)
        y = mha.forward(x)
        self.assertEqual(y.shape, (3, 4))

    def test_parameter_count(self):
        mha = MultiHeadAttention(input_dim=8, d_model=8, num_heads=2, seed=0)
        # w_q (8*8) + b_q 8 + w_k 64+8 + w_v 64+8 + w_o 64+8 = 288
        self.assertEqual(mha.parameter_count(), 8 * 8 * 4 + 8 * 4)

    def test_build_model_attention(self):
        m = build_model([4, 8], [4, 8], [{"type": "attention", "d_model": 8, "num_heads": 2}], seed=0)
        self.assertEqual(m.parameter_count, 288)
        x = Tensor.randn((2, 4, 8), dtype="Float32", seed=1)
        y = m.forward(x)
        self.assertEqual(y.shape, (2, 4, 8))

    def test_backward(self):
        mha = MultiHeadAttention(input_dim=4, d_model=4, num_heads=2, seed=1)
        x = Tensor.ones((2, 2, 4), dtype="Float64", requires_grad=True)
        y = mha.forward(x)
        loss = sum_all(y * y)
        loss.backward()
        self.assertIsNotNone(x.grad)
        self.assertNotEqual(sum(abs(v) for v in x.grad.data), 0)


class TransformerTests(unittest.TestCase):
    def test_forward(self):
        tb = TransformerBlock(d_model=8, num_heads=2, seed=0)
        x = Tensor.randn((2, 4, 8), dtype="Float32", seed=1)
        y = tb.forward(x)
        self.assertEqual(y.shape, (2, 4, 8))

    def test_parameter_count(self):
        tb = TransformerBlock(d_model=8, num_heads=2, seed=0)
        # attn 288 + norm1 16 + norm2 16 + ff1 (8*32+32=288) + ff2 (32*8+8=264) = 872
        self.assertEqual(tb.parameter_count(), 872)

    def test_build_model_transformer(self):
        m = build_model(
            [4, 8],
            [4, 8],
            [{"type": "transformer", "d_model": 8, "num_heads": 2}],
            seed=0,
        )
        x = Tensor.randn((2, 4, 8), dtype="Float32", seed=1)
        y = m.forward(x)
        self.assertEqual(y.shape, (2, 4, 8))

    def test_serialisation_roundtrip(self):
        m = build_model(
            [4, 8],
            [4, 8],
            [{"type": "transformer", "d_model": 8, "num_heads": 2, "d_ff": 16}],
            seed=42,
        )
        arch = m.architecture()
        from peacock.intelligence.layers import model_from_architecture

        m2 = model_from_architecture(arch, seed=42)
        self.assertEqual(m.parameter_count, m2.parameter_count)
        x = Tensor.randn((2, 4, 8), dtype="Float32", seed=99)
        y1 = m.forward(x)
        y2 = m2.forward(x)
        self.assertEqual(y1.tolist(), y2.tolist())


class PositionalEncodingTests(unittest.TestCase):
    def test_shape(self):
        pe = positional_encoding(10, 8)
        self.assertEqual(pe.shape, (10, 8))

    def test_values(self):
        pe = positional_encoding(1, 4)
        # pos 0: sin0=0, cos0=1, sin0=0, cos0=1
        self.assertAlmostEqual(pe.tolist()[0][0], 0.0, places=5)
        self.assertAlmostEqual(pe.tolist()[0][1], 1.0, places=5)

    def test_broadcast_add(self):
        pe = positional_encoding(4, 8)
        x = Tensor.ones((2, 4, 8), dtype="Float32")
        # broadcast (4,8) to (2,4,8)
        y = x + pe
        self.assertEqual(y.shape, (2, 4, 8))


if __name__ == "__main__":
    unittest.main()
