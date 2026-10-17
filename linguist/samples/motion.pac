// Motion primitives are ordinary PEACOCK calls.
module motion_sample

use motion

fn main() -> Unit {
    let steps = motion.spring_steps(0.0, 100.0, 170.0, 26.0, 60, 0.016666666666666666);
    print("samples: " + str(len(steps)));
    print("eased: " + str(motion.ease("ease_in_out_cubic", 0.5)));
}
