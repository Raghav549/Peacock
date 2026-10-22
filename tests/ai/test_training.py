import json
import struct
import tempfile
import unittest

import peacock
from pathlib import Path

from peacock.intelligence.datasets import Dataset, make_dataset, spiral_dataset, xor_dataset
from peacock.intelligence.evaluation import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    evaluate_model,
)
from peacock.intelligence.layers import Dense, build_model
from peacock.intelligence.optim import Adam, SGD, make_optimizer
from peacock.intelligence.serialization import (
    MODEL_MAGIC,
    load_model,
    model_from_bytes,
    model_to_bytes,
    quantization_report,
    quantize_tensor,
    save_model,
)
from peacock.intelligence.tensor import Tensor, TensorError, sum_all
from peacock.intelligence.training import cross_entropy_loss, mse_loss, train_model


class DatasetTests(unittest.TestCase):
    def test_xor_dataset(self):
        data = xor_dataset()
        self.assertEqual(len(data), 4)
        self.assertEqual(data.features.shape, (4, 2))
        self.assertEqual(data.labels.shape, (4, 2))
        self.assertEqual(data.features.tolist(), [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
        self.assertEqual(data.labels.tolist(), [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]])

    def test_spiral_is_deterministic_and_balanced(self):
        first = spiral_dataset(20, 0.1, 7)
        second = spiral_dataset(20, 0.1, 7)
        self.assertEqual(first.features.tolist(), second.features.tolist())
        self.assertEqual(len(first), 40)
        self.assertEqual(sum(first.labels.data[0::2]), 20.0)
        self.assertEqual(sum(first.labels.data[1::2]), 20.0)
        self.assertEqual(first.provenance["licence"], "generated locally; no external data")

    def test_spiral_validation(self):
        with self.assertRaises(TensorError):
            spiral_dataset(0, 0.1, 1)
        with self.assertRaises(TensorError):
            spiral_dataset(10, -0.1, 1)

    def test_custom_dataset(self):
        features = Tensor.from_nested([[1.0, 2.0], [3.0, 4.0]])
        labels = Tensor.from_nested([[1.0], [0.0]])
        data = make_dataset(features, labels, "custom")
        self.assertEqual(len(data), 2)
        self.assertEqual(data.name, "custom")
        self.assertEqual(data.provenance["kind"], "host-supplied")

    def test_dataset_shape_validation(self):
        features = Tensor.from_nested([[1.0, 2.0], [3.0, 4.0]])
        labels = Tensor.from_nested([[1.0], [0.0], [1.0]])
        with self.assertRaises(TensorError):
            make_dataset(features, labels, "bad")

    def test_subset_and_metadata(self):
        data = xor_dataset()
        subset = data.subset([0, 3])
        self.assertEqual(len(subset), 2)
        metadata = data.metadata()
        self.assertEqual(metadata["samples"], 4)
        self.assertEqual(metadata["feature_dim"], 2)


class LayerTests(unittest.TestCase):
    def test_dense_forward(self):
        layer = Dense(2, 3, seed=1)
        out = layer.forward(Tensor.from_nested([[1.0, 2.0]]))
        self.assertEqual(out.shape, (1, 3))
        single = layer.forward(Tensor.from_nested([1.0, 2.0]))
        self.assertEqual(single.shape, (3,))

    def test_sequential_and_parameter_count(self):
        model = build_model((2,), (2,), [(8, "relu"), (2, "linear")], seed=1)
        self.assertEqual(model.parameter_count, 2 * 8 + 8 + 8 * 2 + 2)
        out = model.forward(Tensor.from_nested([[0.0, 1.0]]))
        self.assertEqual(out.shape, (1, 2))

    def test_unknown_activation(self):
        with self.assertRaises(TensorError):
            Dense(2, 3, activation="gelu", seed=1)

    def test_model_forward_shape_mismatch(self):
        model = build_model((2,), (2,), [(2, "linear")], seed=1)
        with self.assertRaises(TensorError):
            model.forward(Tensor.from_nested([[1.0, 2.0, 3.0]]))

    def test_predict_returns_logits(self):
        model = build_model((2,), (2,), [(2, "linear")], seed=1)
        prediction = model.predict(Tensor.from_nested([0.0, 1.0]))
        self.assertEqual(tuple(prediction.shape), (2,))

    def test_rejects_bad_units(self):
        with self.assertRaises(TensorError):
            Dense(2, 0, seed=1)


class LossTests(unittest.TestCase):
    def test_mse_zero_for_identical(self):
        a = Tensor.from_nested([[1.0, 2.0]])
        self.assertAlmostEqual(mse_loss(a, a).item(), 0.0)

    def test_mse_known_value(self):
        a = Tensor.from_nested([[1.0, 2.0]])
        b = Tensor.from_nested([[3.0, 4.0]])
        self.assertAlmostEqual(mse_loss(a, b).item(), 4.0)

    def test_mse_shape_mismatch(self):
        with self.assertRaises(TensorError):
            mse_loss(Tensor.from_nested([[1.0]]), Tensor.from_nested([[1.0, 2.0]]))

    def test_cross_entropy_uniform_logits(self):
        logits = Tensor.from_nested([[0.0, 0.0]])
        labels = Tensor.from_nested([[1.0, 0.0]])
        self.assertAlmostEqual(cross_entropy_loss(logits, labels).item(), 0.6931471805599453, places=6)

    def test_cross_entropy_confidence(self):
        logits = Tensor.from_nested([[10.0, 0.0]])
        labels = Tensor.from_nested([[1.0, 0.0]])
        self.assertLess(cross_entropy_loss(logits, labels).item(), 1e-3)

    def test_cross_entropy_label_shape(self):
        with self.assertRaises(TensorError):
            cross_entropy_loss(Tensor.from_nested([[1.0, 2.0]]), Tensor.from_nested([[1.0]]))

    def test_unknown_objective(self):
        data = xor_dataset()
        model = build_model((2,), (2,), [(2, "linear")], seed=1)
        with self.assertRaises(TensorError):
            train_model(model, data, objective="hinge", epochs=1)


class OptimizerTests(unittest.TestCase):
    def test_sgd_step(self):
        param = Tensor([1.0], (1,), requires_grad=True)
        sum_all(param * 2.0).backward()
        optimiser = SGD([param], learning_rate=0.1)
        optimiser.step()
        self.assertAlmostEqual(param.data[0], 0.8, places=6)
        optimiser.zero_grad()
        self.assertIsNone(param.grad)

    def test_sgd_momentum(self):
        param = Tensor([1.0], (1,), requires_grad=True)
        optimiser = SGD([param], learning_rate=0.1, momentum=0.9)
        sum_all(param * 2.0).backward()
        optimiser.step()
        self.assertAlmostEqual(param.data[0], 0.8, places=6)

    def test_adam_reduces_loss(self):
        weight = Tensor([1.0], (1,), requires_grad=True)
        target = Tensor([0.0], (1,))
        optimiser = Adam([weight], learning_rate=0.1)
        initial = mse_loss(weight, target).item()
        for _ in range(50):
            optimiser.zero_grad()
            loss = mse_loss(weight, target)
            loss.backward()
            optimiser.step()
        self.assertLess(mse_loss(weight, target).item(), initial)

    def test_invalid_learning_rate(self):
        param = Tensor([1.0], (1,), requires_grad=True)
        with self.assertRaises(TensorError):
            SGD([param], learning_rate=0.0)
        with self.assertRaises(TensorError):
            Adam([param], learning_rate=-1.0)

    def test_empty_parameter_list(self):
        with self.assertRaises(TensorError):
            SGD([], learning_rate=0.1)

    def test_make_optimizer(self):
        param = Tensor([1.0], (1,), requires_grad=True)
        self.assertIsInstance(make_optimizer("adam", [param], 0.01), Adam)
        self.assertIsInstance(make_optimizer("sgd", [param], 0.01), SGD)
        with self.assertRaises(TensorError):
            make_optimizer("rmsprop", [param], 0.01)


class TrainingTests(unittest.TestCase):
    def test_xor_training_converges(self):
        data = xor_dataset()
        model = build_model((2,), (2,), [(8, "relu"), (2, "linear")], seed=7)
        report = train_model(model, data, epochs=300, learning_rate=0.05, batch_size=4, seed=7)
        self.assertEqual(len(report.losses), 300)
        self.assertLess(report.final_loss, 0.01)
        self.assertEqual(report.final_accuracy, 1.0)
        self.assertEqual(len(report.accuracies), 300)

    def test_report_metadata(self):
        data = xor_dataset()
        model = build_model((2,), (2,), [(4, "relu"), (2, "linear")], seed=1)
        report = train_model(model, data, epochs=5, batch_size=2, seed=1)
        payload = report.to_dict()
        for key in ("epochs", "final_loss", "final_accuracy", "elapsed_seconds", "parameter_count", "dataset"):
            self.assertIn(key, payload)
        self.assertEqual(payload["epochs"], 5)
        self.assertEqual(payload["dataset"]["samples"], 4)

    def test_invalid_epochs(self):
        data = xor_dataset()
        model = build_model((2,), (2,), [(2, "linear")], seed=1)
        with self.assertRaises(TensorError):
            train_model(model, data, epochs=0)

    def test_invalid_optimiser(self):
        data = xor_dataset()
        model = build_model((2,), (2,), [(2, "linear")], seed=1)
        with self.assertRaises(TensorError):
            train_model(model, data, optimiser="rmsprop", epochs=1)

    def test_feature_dimension_mismatch(self):
        data = xor_dataset()
        model = build_model((3,), (2,), [(2, "linear")], seed=1)
        with self.assertRaises(TensorError):
            train_model(model, data, epochs=1)

    def test_evaluation_metrics(self):
        logits = Tensor.from_nested([[2.0, 0.0], [0.0, 2.0], [2.0, 0.0], [2.0, 0.0]])
        labels = Tensor.from_nested([[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]])
        self.assertAlmostEqual(accuracy_score(logits, labels), 0.75)
        matrix = confusion_matrix(logits, labels, 2)
        self.assertEqual(len(matrix), 2)
        self.assertEqual(sum(sum(row) for row in matrix), 4)
        report = classification_report(logits, labels)
        self.assertIn("macro_f1", report)
        self.assertEqual(report["samples"], 4)


class SerializationRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.model = build_model((2,), (2,), [(6, "relu"), (2, "linear")], seed=5)

    def test_bytes_roundtrip_preserves_predictions(self):
        data = Tensor.from_nested([[0.2, -0.4], [0.9, 0.1]])
        before = self.model.forward(data).tolist()
        blob = model_to_bytes(self.model)
        header_length = struct.unpack("<I", blob[10:14])[0]
        header = json.loads(blob[14:14 + header_length])
        self.assertEqual(header["format_version"], 1)
        self.assertEqual(header["language_version"], peacock.LANGUAGE_VERSION)
        restored, metadata = model_from_bytes(blob)
        after = restored.forward(data).tolist()
        for row_before, row_after in zip(before, after):
            for a, b in zip(row_before, row_after):
                self.assertAlmostEqual(a, b, places=5)
        self.assertIsInstance(metadata, dict)

    def test_metadata_roundtrip(self):
        blob = model_to_bytes(self.model, {"name": "unit-test"})
        restored, metadata = model_from_bytes(blob)
        self.assertEqual(metadata.get("name"), "unit-test")

    def test_container_magic(self):
        blob = model_to_bytes(self.model)
        self.assertTrue(blob.startswith(MODEL_MAGIC))

    def test_corrupt_payload_rejected(self):
        blob = bytearray(model_to_bytes(self.model))
        blob[-10] ^= 0xFF
        with self.assertRaises((ValueError, TensorError)):
            model_from_bytes(bytes(blob))

    def test_truncated_rejected(self):
        with self.assertRaises((ValueError, TensorError)):
            model_from_bytes(model_to_bytes(self.model)[:40])

    def test_save_and_load_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.ज्ञान"
            size = save_model(self.model, str(path))
            self.assertEqual(size, path.stat().st_size)
            restored = load_model(str(path))
            data = Tensor.from_nested([[1.0, 0.0]])
            for a, b in zip(self.model.forward(data).data, restored.forward(data).data):
                self.assertAlmostEqual(a, b, places=5)

    def test_quantisation_shrinks_payload(self):
        report = quantization_report(self.model)
        self.assertIn("compression_ratio", report)
        self.assertGreater(report["compression_ratio"], 1.0)

    def test_quantize_individual_tensor(self):
        q = quantize_tensor(self.model.parameters()[0])
        self.assertTrue(q.values)
        self.assertLessEqual(max(q.values), 127)
        self.assertGreaterEqual(min(q.values), -127)
        self.assertGreater(q.scale, 0.0)


if __name__ == "__main__":
    unittest.main()
