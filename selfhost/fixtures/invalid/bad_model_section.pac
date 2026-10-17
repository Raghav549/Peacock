module invalid_bad_model_section

use nn

model Broken {
    input x: Tensor<Float32, [1]>
    weights {
        Dense(units: 1)
    }
}
