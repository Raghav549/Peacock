import math
import unittest

from peacock.intelligence import tensor as T
from peacock.intelligence.tensor import Tensor, TensorError


def vec(values, **kwargs):
    return Tensor(values, (len(values),), **kwargs)


class ConstructionTests(unittest.TestCase):
    def test_from_nested_and_metadata(self):
        t = Tensor.from_nested([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(t.shape, (2, 2))
        self.assertEqual(t.size, 4)
        self.assertEqual(t.rank, 2)
        self.assertEqual(t.dtype, "Float32")
        self.assertEqual(t.tolist(), [[1.0, 2.0], [3.0, 4.0]])

    def test_flat_construction(self):
        t = Tensor([1.0, 2.0, 3.0], (3,))
        self.assertEqual(t.tolist(), [1.0, 2.0, 3.0])

    def test_size_mismatch_rejected(self):
        with self.assertRaises(TensorError):
            Tensor([1.0, 2.0, 3.0], (2, 2))

    def test_ragged_input_rejected(self):
        with self.assertRaises(TensorError):
            Tensor.from_nested([[1.0], [1.0, 2.0]])

    def test_bad_dtype_rejected(self):
        with self.assertRaises(TensorError):
            Tensor([1.0], (1,), dtype="Float16")

    def test_float32_rounding_at_construction(self):
        t = Tensor([0.1], (1,), dtype="Float32")
        self.assertNotEqual(t.data[0], 0.1)
        self.assertAlmostEqual(t.data[0], 0.1, places=7)

    def test_float64_preserves(self):
        t = Tensor([0.1], (1,), dtype="Float64")
        self.assertEqual(t.data[0], 0.1)

    def test_int32_construction_truncates(self):
        t = Tensor([1.9, -1.9], (2,), dtype="Int32")
        self.assertEqual(t.tolist(), [1, -1])

    def test_bool_tensor(self):
        t = Tensor([True, False], (2,), dtype="Bool")
        self.assertEqual(t.tolist(), [True, False])

    def test_integer_tensors_cannot_require_grad(self):
        with self.assertRaises(TensorError):
            Tensor([1, 2], (2,), dtype="Int32", requires_grad=True)

    def test_factories(self):
        self.assertEqual(Tensor.zeros((2, 3)).tolist(), [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        self.assertEqual(Tensor.ones((2,), dtype="Int32").tolist(), [1, 1])
        self.assertEqual(Tensor.full((2, 2), 7.0).tolist(), [[7.0, 7.0], [7.0, 7.0]])
        self.assertEqual(Tensor.arange(0, 5, 2).tolist(), [0, 2, 4])
        self.assertEqual(Tensor.eye(3).tolist(), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    def test_factory_rejects_negative_shape(self):
        with self.assertRaises(TensorError):
            Tensor.zeros((2, -1))

    def test_reshape(self):
        t = Tensor([1.0, 2.0, 3.0, 4.0], (4,))
        self.assertEqual(T.reshape(t, (2, 2)).shape, (2, 2))
        with self.assertRaises(TensorError):
            T.reshape(t, (2, -1))  # inferred (-1) dimensions are not part of v0.1
        with self.assertRaises(TensorError):
            T.reshape(t, (3, 2))

    def test_transpose(self):
        t = Tensor.from_nested([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        self.assertEqual(T.transpose(t).tolist(), [[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]])
        self.assertEqual(T.transpose(vec([1.0, 2.0])).shape, (2,))

    def test_matmul(self):
        a = Tensor.from_nested([[1.0, 2.0], [3.0, 4.0]])
        b = Tensor.from_nested([[5.0, 6.0], [7.0, 8.0]])
        self.assertEqual(T.matmul(a, b).tolist(), [[19.0, 22.0], [43.0, 50.0]])
        self.assertEqual((a @ b).tolist(), [[19.0, 22.0], [43.0, 50.0]])
        with self.assertRaises(TensorError):
            T.matmul(a, Tensor.from_nested([[1.0, 2.0, 3.0]]))

    def test_elementwise_and_broadcast(self):
        a = Tensor.from_nested([[1.0, 2.0], [3.0, 4.0]])
        b = vec([10.0, 20.0])
        self.assertEqual(T.add(a, b).tolist(), [[11.0, 22.0], [13.0, 24.0]])
        self.assertEqual(T.mul(a, 2.0).tolist(), [[2.0, 4.0], [6.0, 8.0]])
        self.assertEqual(T.sub(a, a).tolist(), [[0.0, 0.0], [0.0, 0.0]])
        self.assertEqual(T.divide(a, 2.0).tolist(), [[0.5, 1.0], [1.5, 2.0]])
        with self.assertRaises(TensorError):
            T.add(a, vec([1.0, 2.0, 3.0]))

    def test_division_by_zero(self):
        with self.assertRaises(TensorError):
            T.divide(vec([1.0]), 0.0)

    def test_unary_ops(self):
        t = vec([-1.5, 0.0, 1.5])
        self.assertEqual(T.absolute(t).tolist(), [1.5, 0.0, 1.5])
        self.assertEqual(T.negative(t).tolist(), [1.5, -0.0, -1.5])

    def test_reductions(self):
        t = Tensor.from_nested([[1.0, 2.0], [3.0, 4.0]])
        self.assertAlmostEqual(T.sum_all(t).item(), 10.0)
        self.assertAlmostEqual(T.mean_all(t).item(), 2.5)
        self.assertAlmostEqual(T.max_value(t), 4.0)
        self.assertAlmostEqual(T.min_value(t), 1.0)
        with self.assertRaises(TensorError):
            T.max_value(Tensor.zeros((0,)))

    def test_softmax_sums_to_one_and_is_stable(self):
        t = Tensor([1000.0, 1000.0, 1000.0], (1, 3))
        out = T.softmax(t)
        self.assertAlmostEqual(sum(out.data), 1.0, places=6)
        self.assertAlmostEqual(out.data[0], 1 / 3, places=6)

    def test_softmax_rows(self):
        t = Tensor.from_nested([[0.0, 1.0], [1.0, 0.0]])
        out = T.softmax(t)
        self.assertAlmostEqual(sum(out.data[0:2]), 1.0, places=6)
        self.assertAlmostEqual(sum(out.data[2:4]), 1.0, places=6)

    def test_log_softmax_matches_log_of_softmax(self):
        t = vec([0.5, -1.0, 2.0])
        direct = T.log_softmax(t)
        composed = T.log(T.softmax(t))
        for a, b in zip(direct.data, composed.data):
            self.assertAlmostEqual(a, b, places=5)

    def test_activations(self):
        t = vec([-1.0, 0.0, 2.0])
        self.assertEqual(T.relu(t).tolist(), [0.0, 0.0, 2.0])
        self.assertAlmostEqual(T.tanh(t).data[2], math.tanh(2.0), places=6)
        self.assertAlmostEqual(T.sigmoid(t).data[2], 1 / (1 + math.exp(-2.0)), places=6)
        self.assertAlmostEqual(T.exp(t).data[2], math.exp(2.0), places=6)
        self.assertAlmostEqual(T.log(T.exp(t)).data[2], 2.0, places=6)
        self.assertAlmostEqual(T.sqrt(vec([9.0])).data[0], 3.0, places=6)

    def test_power(self):
        self.assertEqual(T.power(vec([2.0, 3.0]), 2.0).tolist(), [4.0, 9.0])

    def test_argmax_and_row_selection(self):
        logits = Tensor.from_nested([[0.1, 0.9], [0.8, 0.2]])
        self.assertEqual(T.argmax_last(logits), [1, 0])
        selected = T.select_rows(logits, [1]).tolist()
        self.assertAlmostEqual(selected[0][0], 0.8, places=6)
        self.assertAlmostEqual(selected[0][1], 0.2, places=6)

    def test_max_abs_diff(self):
        a = vec([1.0, 2.0])
        b = vec([1.0, 2.5])
        self.assertAlmostEqual(T.max_abs_diff(a, b), 0.5)
        with self.assertRaises(TensorError):
            T.max_abs_diff(a, Tensor.from_nested([[1.0, 2.0]]))


class AutodiffTests(unittest.TestCase):
    def test_gradient_of_square(self):
        x = vec([2.0, 3.0], requires_grad=True)
        y = T.sum_all(T.mul(x, x))
        y.backward()
        self.assertEqual(x.grad.tolist(), [4.0, 6.0])

    def test_gradient_accumulates(self):
        x = vec([2.0], requires_grad=True)
        T.sum_all(T.mul(x, 3.0)).backward()
        T.sum_all(T.mul(x, 3.0)).backward()
        self.assertAlmostEqual(x.grad.data[0], 6.0, places=6)

    def test_zero_grad(self):
        x = vec([2.0], requires_grad=True)
        T.sum_all(T.mul(x, x)).backward()
        x.zero_grad()
        self.assertIsNone(x.grad)

    def test_gradient_through_matmul(self):
        a = Tensor.from_nested([[1.0, 2.0]], requires_grad=True)
        b = Tensor.from_nested([[3.0], [4.0]], requires_grad=True)
        T.sum_all(T.matmul(a, b)).backward()
        self.assertEqual(b.grad.tolist(), [[1.0], [2.0]])
        self.assertEqual(a.grad.tolist(), [[3.0, 4.0]])

    def test_gradient_through_softmax_sums_to_zero(self):
        x = Tensor.from_nested([[1.0, 2.0, 3.0]], requires_grad=True)
        out = T.softmax(x)
        out.backward(Tensor.ones(out.shape))
        self.assertAlmostEqual(sum(x.grad.data), 0.0, places=5)

    def test_gradcheck_against_finite_differences(self):
        x = Tensor.from_nested([[0.3, -0.7]], requires_grad=True)
        w = Tensor.from_nested([[1.2], [-0.4]], requires_grad=True)

        def loss():
            return T.sum_all(T.log(T.softmax(T.matmul(x, w))))

        loss().backward()
        analytic = x.grad.data[0]
        eps = 1e-6
        original = x.data[0]
        x.data[0] = original + eps
        plus = loss().item()
        x.data[0] = original - eps
        minus = loss().item()
        x.data[0] = original
        numeric = (plus - minus) / (2 * eps)
        self.assertAlmostEqual(analytic, numeric, places=5)

    def test_backward_without_requires_grad_is_error(self):
        with self.assertRaises(TensorError):
            T.sum_all(vec([1.0])).backward()

    def test_backward_on_non_scalar_requires_gradient(self):
        x = vec([1.0, 2.0], requires_grad=True)
        with self.assertRaises(TensorError):
            T.mul(x, 2.0).backward()

    def test_gradient_shape_must_match(self):
        x = vec([1.0, 2.0], requires_grad=True)
        with self.assertRaises(TensorError):
            T.mul(x, 2.0).backward(Tensor.ones((3,)))

    def test_detach_blocks_gradients(self):
        x = vec([1.0], requires_grad=True)
        y = T.sum_all(T.mul(x, 2.0).detach())
        self.assertFalse(y.requires_grad)
        with self.assertRaises(TensorError):
            y.backward()

    def test_clone_keeps_grad_flag_but_detach_drops_it(self):
        x = vec([1.0], requires_grad=True)
        cloned = x.clone()
        self.assertTrue(cloned.requires_grad)
        detached = x.detach()
        self.assertFalse(detached.requires_grad)
        y = T.sum_all(T.mul(detached, 2.0))
        self.assertFalse(y.requires_grad)
        with self.assertRaises(TensorError):
            y.backward()


class SerializationTests(unittest.TestCase):
    def test_tolist_roundtrip(self):
        values = [[[1.0, 2.0]], [[3.0, 4.0]]]
        self.assertEqual(Tensor.from_nested(values).tolist(), values)

    def test_repr(self):
        text = repr(Tensor.from_nested([[1.0, 2.0]]))
        self.assertIn("Float32", text)
        self.assertIn("1", text)
        self.assertIn("2", text)

    def test_clone_is_independent(self):
        a = vec([1.0, 2.0])
        b = a.clone()
        b.data[0] = 9.0
        self.assertEqual(a.data[0], 1.0)

    def test_from_nested_int_dtype(self):
        t = Tensor.from_nested([1, 2, 3], dtype="Int32")
        self.assertEqual(t.dtype, "Int32")
        self.assertEqual(t.tolist(), [1, 2, 3])

    def test_item_requires_single_element(self):
        with self.assertRaises(TensorError):
            vec([1.0, 2.0]).item()
        self.assertEqual(Tensor([7.0], (1,)).item(), 7.0)

    def test_gelu_and_layer_norm_finite_difference_gradients(self):
        from peacock.intelligence.tensor import cosine_similarity, gelu, layer_norm, sum_all

        x = Tensor([-1.2, -0.3, 0.4, 1.5], (2, 2), "Float64", requires_grad=True)
        y = sum_all(layer_norm(gelu(x)))
        y.backward()
        assert x.grad is not None
        eps = 1e-6
        for idx in range(x.size):
            plus = list(x.data)
            minus = list(x.data)
            plus[idx] += eps
            minus[idx] -= eps
            f_plus = sum_all(layer_norm(gelu(Tensor(plus, (2, 2), "Float64")))).item()
            f_minus = sum_all(layer_norm(gelu(Tensor(minus, (2, 2), "Float64")))).item()
            numeric = (f_plus - f_minus) / (2.0 * eps)
            self.assertAlmostEqual(x.grad.data[idx], numeric, places=6)

        a = Tensor([1.0, 0.0, 1.0], (3,), "Float64")
        b = Tensor([1.0, 0.0, 1.0], (3,), "Float64")
        c = Tensor([-1.0, 0.0, -1.0], (3,), "Float64")
        self.assertAlmostEqual(cosine_similarity(a, b), 1.0, places=7)
        self.assertAlmostEqual(cosine_similarity(a, c), -1.0, places=7)



if __name__ == "__main__":
    unittest.main()
