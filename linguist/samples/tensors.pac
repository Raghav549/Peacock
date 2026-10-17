// Differentiable tensors and a gradient check.
module tensor_sample

use nn

fn main() -> Unit {
    capability compute;
    let x = tensor([[1.0, 2.0], [3.0, 4.0]]);
    let w = nn.parameter([[0.1, -0.2], [0.3, 0.4]]);
    let target = tensor([[1.0, 0.0], [0.0, 1.0]]);
    let loss = nn.mse(x.matmul(w), target);
    loss.backward();
    print("loss: " + str(loss.item()));
    print("gradient: " + str(w.grad));
}
