// Motion primitives: spring integration and easing, computed by PEACOCK.
module motion_demo

use motion

fn main() -> Unit {
    let values = motion.spring_steps(0.0, 100.0, 170.0, 26.0, 90, 0.016666666666666666);
    print("spring samples: " + str(len(values)));
    print("first: " + str(values.get(0)));
    print("last: " + str(values.get(89)));
    print("ease in-out cubic at 0.5: " + str(motion.ease("ease_in_out_cubic", 0.5)));
    print("ease out back at 0.5: " + str(motion.ease("ease_out_back", 0.5)));
}
