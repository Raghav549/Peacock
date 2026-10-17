// Deterministic procedural colour: render an aurora to a real PNG.
module aurora

use colour
use graphics

fn main() -> Unit {
    capability fs;
    let canvas = graphics.canvas(960, 540);
    let palette = [
        colour.oklch(0.55, 0.18, 160.0),
        colour.oklch(0.72, 0.20, 285.0),
        colour.oklch(0.62, 0.16, 60.0)
    ];
    graphics.gradient(canvas, palette, 35.0);
    graphics.aurora(canvas, 1.5, 42);
    graphics.save(canvas, "examples/out/aurora.png");
    print("wrote examples/out/aurora.png");
}
