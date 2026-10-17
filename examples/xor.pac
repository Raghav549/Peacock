// Train a small neural network on XOR, entirely through PEACOCK syntax.
module xor_net

use nn

model XorNet {
    input x: Tensor<Float32, [2]>
    output y: Tensor<Float32, [2]>
    stack {
        Dense(units: 8, activation: relu)
        Dense(units: 2)
    }
}

training XorTraining {
    objective: "cross_entropy"
    optimiser: "adam"
    epochs: 400
    learning_rate: 0.05
    batch_size: 4
    seed: 7
}

fn main() -> Unit {
    capability compute;
    let data = nn.xor();
    let net = XorNet.init(seed: 7);
    let losses = XorTraining.run(net, data);
    let accuracy = XorTraining.evaluate(net, data);
    print("epochs: " + str(len(losses)));
    print("final loss: " + str(nn.loss(net, data, loss: "cross_entropy")));
    print("accuracy: " + str(accuracy));
}
