import unittest

from peacock.frontend.canvas import Canvas
from peacock.frontend.colour import Color
from peacock.frontend.scene3d import Scene3D, Scene3DError, cube_mesh, sphere_mesh


class MeshTests(unittest.TestCase):
    def test_cube_and_sphere_mesh_counts(self):
        self.assertEqual(len(cube_mesh().faces), 12)
        self.assertEqual(len(cube_mesh().vertices), 24)
        self.assertEqual(len(sphere_mesh(1.0, 8, 4).faces), 64)
        self.assertEqual(len(sphere_mesh(1.0, 8, 4).vertices), 40)

    def test_mesh_validation(self):
        for args in ((0.0, 8, 4), (1.0, 2, 4), (1.0, 8, 1)):
            with self.subTest(args=args), self.assertRaises(Scene3DError):
                sphere_mesh(*args)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.white = Color.from_hex("#ffffff")

    def test_cube_renders_non_background_pixels(self):
        scene = Scene3D()
        scene.cube(0, 0, 0, 1.5, Color.from_hex("#ff0000"))
        scene.light(2, 3, 4, self.white, 1.5)
        canvas = Canvas(64, 64)
        canvas.clear(Color.from_hex("#101820"))
        scene.render(canvas)
        self.assertEqual(scene.last_triangle_count, 6)
        self.assertGreater(canvas.pixel_straight(32, 32)[0], 0.2)
        self.assertEqual(scene.triangle_count, 12)

    def test_depth_buffer_occludes_distant_object(self):
        scene = Scene3D()
        scene.cube(0, 0, 0, 1, Color.from_hex("#0000ff"))
        scene.cube(0, 0, 1, 1, Color.from_hex("#ff0000"))
        scene.light(0, 2, 5, self.white, 2)
        canvas = Canvas(64, 64)
        scene.render(canvas, 0, 0, 5)
        r, _g, b, _a = canvas.pixel_straight(32, 32)
        self.assertGreater(r, b * 10)

    def test_sphere_renders_with_lighting(self):
        scene = Scene3D()
        scene.sphere(0, 0, 0, 1, Color.from_hex("#00ff00"), 12, 6)
        scene.light(2, 3, 4, self.white, 2)
        canvas = Canvas(64, 64)
        scene.render(canvas, 0, 0, 5)
        self.assertGreater(scene.last_triangle_count, 20)
        self.assertGreater(canvas.pixel_straight(32, 32)[1], 0.2)

    def test_rotation_light_limits_and_camera_validation(self):
        scene = Scene3D()
        node = scene.cube(0, 0, 0, 1, self.white)
        scene.rotate(node, 10, 20, 30)
        self.assertEqual(scene.objects[node].rotation.x, 10)
        for index in range(16):
            scene.light(index, 1, 2, self.white)
        with self.assertRaises(Scene3DError):
            scene.light(0, 0, 0, self.white)
        with self.assertRaises(Scene3DError):
            scene.render(Canvas(8, 8), distance=0)


if __name__ == "__main__":
    unittest.main()
