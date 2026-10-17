// Differentiable computation in PEACOCK: matmul, loss, reverse-mode gradients.
module tensors

use nn

fn main() -> Unit {
    capability compute;

    let x = tensor([[1.0, 2.0], [3.0, 4.0]]);
    let column = tensor([[0.5], [1.5]]);
    let projected = x.matmul(column);
    print("matmul: " + str(projected));
    print("shape: " + str(projected.shape));
    print("softmax: " + str(tensor([[1.0, 2.0, 3.0]]).softmax()));

    let weights = nn.parameter([[0.1, -0.2], [0.3, 0.4]]);
    let targets = tensor([[1.0, 0.0], [0.0, 1.0]]);
    let predictions = x.matmul(weights);
    let loss = nn.mse(predictions, targets);
    print("loss: " + str(loss.item()));
    loss.backward();
    print("weight gradient: " + str(weights.grad));

    // Analytic check: for mean-squared error, dL/dW = X^T * (2/N) * (P - T).
    let expected = x.transpose().matmul((predictions - targets) * 0.5);
    print("autodiff gradient: " + str(weights.grad));
    print("closed-form gradient: " + str(expected));
    print("max abs difference: " + str(nn.max_abs_diff(weights.grad, expected)));
}
