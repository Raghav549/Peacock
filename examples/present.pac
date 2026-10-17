// Present animated frames to the host's presentation backend.
//
// Run with:  ./bin/peacock run examples/present.pac --grant ui --present out/preview
//
// The host attaches a backend (the CLI attaches a static-web backend) and each
// graphics.present call hands it the current canvas. The program does not know
// or care whether the backend writes PNGs, serves HTTP or draws a window.
module present_demo

use colour
use graphics

fn main() -> Unit {
    capability ui;

    let canvas = graphics.canvas(320, 180);
    let backdrop = [
        colour.oklch(0.20, 0.06, 250.0),
        colour.oklch(0.34, 0.10, 290.0)
    ];
    let mut frame = 0;
    while frame < 4 {
        let t = float(frame) / 3.0;
        graphics.gradient(canvas, backdrop, 30.0 + 40.0 * t);
        graphics.circle(canvas, 80.0 + 60.0 * t, 90.0, 26.0, colour.oklch(0.78, 0.16, 60.0));
        graphics.circle(canvas, 240.0 - 40.0 * t, 70.0, 14.0, colour.oklch(0.72, 0.14, 200.0));
        graphics.present(canvas);
        frame += 1;
    }
    print("presented " + str(frame) + " frames");
}
