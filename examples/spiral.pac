// Train a small classifier on a synthetic two-arm spiral.
module spiral_net

use nn

model SpiralNet {
    input features: Tensor<Float32, [2]>
    output scores: Tensor<Float32, [2]>
    stack {
        Dense(units: 24, activation: relu)
        Dense(units: 24, activation: relu)
        Dense(units: 2)
    }
}

training SpiralTraining {
    objective: "cross_entropy"
    optimiser: "adam"
    epochs: 250
    learning_rate: 0.02
    batch_size: 16
    seed: 3
}

fn main() -> Unit {
    capability compute;

    let data = nn.spiral(24, 0.1, 3);
    let net = SpiralNet.init(seed: 3);
    print("samples: " + str(data.size));
    let losses = SpiralTraining.run(net, data);
    print("epochs: " + str(len(losses)));
    print("final loss: " + str(nn.loss(net, data, loss: "cross_entropy")));
    print("accuracy: " + str(SpiralTraining.evaluate(net, data)));
}
