import math
import unittest

from peacock.frontend.colour import Color
from peacock.frontend.easing import EASINGS, clamp_unit, cubic_bezier, ease
from peacock.frontend.layout import LayoutChild, Rect, layout_column, layout_row
from peacock.frontend.physics import Body, World
from peacock.frontend.spring import SpringConfig, is_settled, settle, step_spring
from peacock.frontend.timeline import Keyframe, Timeline, Track


class EasingTests(unittest.TestCase):
    def test_endpoints_for_all_easings(self):
        for name in EASINGS:
            self.assertAlmostEqual(ease(name, 0.0), 0.0, places=9)
            self.assertAlmostEqual(ease(name, 1.0), 1.0, places=9)

    def test_known_values(self):
        self.assertEqual(ease("linear", 0.25), 0.25)
        self.assertAlmostEqual(ease("ease_in_out_cubic", 0.5), 0.5, places=12)
        self.assertAlmostEqual(ease("ease_in_quad", 0.5), 0.25, places=12)
        self.assertAlmostEqual(ease("ease_out_quad", 0.5), 0.75, places=12)

    def test_clamping(self):
        self.assertEqual(clamp_unit(-1.0), 0.0)
        self.assertEqual(clamp_unit(2.0), 1.0)
        self.assertEqual(ease("linear", 2.0), 1.0)

    def test_unknown_easing(self):
        with self.assertRaises(ValueError):
            ease("wobble", 0.5)

    def test_non_finite(self):
        with self.assertRaises(ValueError):
            ease("linear", float("nan"))
        with self.assertRaises(ValueError):
            clamp_unit(float("inf"))

    def test_cubic_bezier_endpoints_and_monotonicity(self):
        self.assertEqual(cubic_bezier(0.42, 0.0, 0.58, 1.0, 0.0), 0.0)
        self.assertEqual(cubic_bezier(0.42, 0.0, 0.58, 1.0, 1.0), 1.0)
        previous = -1.0
        for i in range(21):
            value = cubic_bezier(0.25, 0.1, 0.25, 1.0, i / 20.0)
            self.assertGreaterEqual(value, previous - 1e-9)
            previous = value


class SpringTests(unittest.TestCase):
    def test_config_validation(self):
        with self.assertRaises(ValueError):
            SpringConfig(stiffness=0.0)
        with self.assertRaises(ValueError):
            SpringConfig(damping=-1.0)
        with self.assertRaises(ValueError):
            SpringConfig(mass=0.0)

    def test_settle_converges(self):
        config = SpringConfig(170.0, 26.0, 1.0)
        values = settle(0.0, 100.0, config, 120)
        self.assertEqual(values[0], 0.0)
        self.assertAlmostEqual(values[-1], 100.0, places=2)
        self.assertLessEqual(max(values), 112.0)  # bounded overshoot
        self.assertTrue(all(math.isfinite(v) for v in values))

    def test_step_rejects_bad_dt(self):
        with self.assertRaises(ValueError):
            step_spring(0.0, 0.0, 1.0, SpringConfig(), 0.0)

    def test_is_settled(self):
        self.assertTrue(is_settled(100.0, 100.0, 0.0))
        self.assertFalse(is_settled(90.0, 100.0, 0.0))

    def test_high_stiffness_remains_finite(self):
        values = settle(0.0, 1.0, SpringConfig(2000.0, 10.0, 0.5), 200)
        self.assertTrue(all(math.isfinite(v) for v in values))


class TimelineTests(unittest.TestCase):
    def test_numeric_interpolation(self):
        track = Track([Keyframe(0.0, 0.0, "linear"), Keyframe(1.0, 10.0, "linear")])
        self.assertEqual(track.duration, 1.0)
        self.assertAlmostEqual(track.sample(0.5), 5.0, places=9)
        self.assertEqual(track.sample(-1.0), 0.0)
        self.assertEqual(track.sample(2.0), 10.0)

    def test_easing_applied(self):
        track = Track([Keyframe(0.0, 0.0, "linear"), Keyframe(1.0, 10.0, "ease_in_quad")])
        self.assertAlmostEqual(track.sample(0.5), 2.5, places=9)

    def test_loop_wraps(self):
        track = Track([Keyframe(0.0, 0.0, "linear"), Keyframe(2.0, 2.0, "linear")], loop=True)
        self.assertAlmostEqual(track.sample(3.0), 1.0, places=9)
        self.assertAlmostEqual(track.sample(5.0), 1.0, places=9)

    def test_color_interpolation(self):
        a = Color.from_srgb(1.0, 0.0, 0.0)
        b = Color.from_srgb(0.0, 0.0, 1.0)
        track = Track([Keyframe(0.0, a, "linear"), Keyframe(1.0, b, "linear")])
        mid = track.sample(0.5)
        self.assertIsInstance(mid, Color)
        self.assertTrue(mid.in_gamut(tolerance=1e-3))

    def test_invalid_tracks(self):
        with self.assertRaises(ValueError):
            Track([])
        with self.assertRaises(ValueError):
            Track([Keyframe(1.0, 1.0), Keyframe(1.0, 2.0)])
        with self.assertRaises(ValueError):
            Track([Keyframe(0.0, "text")])

    def test_timeline_collects_tracks(self):
        timeline = Timeline()
        timeline.add("opacity", Track([Keyframe(0.0, 0.0), Keyframe(1.0, 1.0)]))
        timeline.add("offset", Track([Keyframe(0.0, 0.0), Keyframe(2.0, 20.0)]))
        self.assertEqual(timeline.duration, 2.0)
        sample = timeline.sample(1.0)
        self.assertEqual(set(sample), {"opacity", "offset"})
        self.assertAlmostEqual(sample["opacity"], 1.0)
        with self.assertRaises(ValueError):
            timeline.add("opacity", Track([Keyframe(0.0, 0.0)]))


class LayoutTests(unittest.TestCase):
    def test_row_distributes_growth(self):
        children = [LayoutChild(20.0, 10.0, grow=1.0), LayoutChild(40.0, 10.0, grow=2.0)]
        result = layout_row(children, 100.0)
        self.assertAlmostEqual(result.rects[0].width, 20.0 + 40.0 / 3.0, places=6)
        self.assertAlmostEqual(result.rects[1].width, 40.0 + 80.0 / 3.0, places=6)
        self.assertAlmostEqual(result.overflow, 0.0)

    def test_row_padding_and_gap(self):
        children = [LayoutChild(10.0, 5.0), LayoutChild(10.0, 5.0)]
        result = layout_row(children, 50.0, padding=5.0, gap=4.0, origin_x=100.0, origin_y=20.0)
        self.assertEqual(result.rects[0].x, 105.0)
        self.assertEqual(result.rects[0].y, 25.0)
        self.assertEqual(result.rects[1].x, 119.0)

    def test_row_overflow(self):
        children = [LayoutChild(80.0, 5.0), LayoutChild(40.0, 5.0)]
        result = layout_row(children, 100.0)
        self.assertGreater(result.overflow, 0.0)

    def test_column(self):
        children = [LayoutChild(10.0, 20.0, grow=1.0), LayoutChild(10.0, 20.0)]
        result = layout_column(children, 100.0, gap=5.0)
        self.assertEqual(result.rects[0].width, 10.0)
        self.assertGreater(result.rects[1].y, result.rects[0].y)

    def test_min_size(self):
        result = layout_row([LayoutChild(5.0, 5.0, min_width=20.0)], 100.0)
        self.assertEqual(result.rects[0].width, 20.0)

    def test_negative_dimensions(self):
        with self.assertRaises(ValueError):
            layout_row([], -1.0)
        with self.assertRaises(ValueError):
            LayoutChild(-1.0, 5.0)


class PhysicsTests(unittest.TestCase):
    def test_gravity_and_resting_contact(self):
        world = World(320.0, 200.0)
        body = world.add(Body(10.0, 10.0, 20.0, 20.0))
        for _ in range(600):
            world.step(1.0 / 120.0)
        self.assertAlmostEqual(body.bottom, 200.0, delta=0.5)
        self.assertLess(abs(body.vy), 20.0)

    def test_static_body_does_not_move(self):
        world = World(100.0, 100.0)
        wall = world.add(Body(0.0, 0.0, 10.0, 100.0, static=True))
        for _ in range(100):
            world.step(1.0 / 120.0)
        self.assertEqual((wall.x, wall.y), (0.0, 0.0))

    def test_determinism(self):
        def simulate():
            world = World(200.0, 200.0)
            world.add(Body(50.0, 10.0, 20.0, 20.0, vx=40.0, restitution=0.5))
            for _ in range(300):
                world.step(1.0 / 120.0)
            return [(b.x, b.y, b.vx, b.vy) for b in world.bodies]

        self.assertEqual(simulate(), simulate())

    def test_invalid_body(self):
        with self.assertRaises(ValueError):
            Body(0.0, 0.0, 0.0, 10.0)
        with self.assertRaises(ValueError):
            Body(0.0, 0.0, 10.0, 10.0, restitution=2.0)

    def test_invalid_step(self):
        world = World(100.0, 100.0)
        with self.assertRaises(ValueError):
            world.step(0.0)
        with self.assertRaises(ValueError):
            world.step(1.0)


if __name__ == "__main__":
    unittest.main()
