"""Original deterministic software 3-D triangle renderer for PEACOCK.

Features: indexed triangle meshes, cube/UV-sphere construction, object and scene
rotations, perspective projection, back-face culling, a depth buffer, multiple
point lights, Lambertian diffuse and a small Blinn–Phong specular term.  This is
a CPU renderer, not a claim of GPU, ray-tracing or physically based rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .canvas import Canvas
from .colour import Color


class Scene3DError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def scale(self, value: float) -> "Vec3":
        return Vec3(self.x * value, self.y * value, self.z * value)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def normalized(self) -> "Vec3":
        length = math.sqrt(self.dot(self))
        return self.scale(1.0 / length) if length > 1e-15 else Vec3(0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class Mesh:
    vertices: tuple[Vec3, ...]
    faces: tuple[tuple[int, int, int], ...]


@dataclass(slots=True)
class Object3D:
    mesh: Mesh
    position: Vec3
    color: Color
    rotation: Vec3 = Vec3(0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class PointLight:
    position: Vec3
    color: Color
    intensity: float


def _finite(values: tuple[float, ...], name: str) -> None:
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
        raise Scene3DError(f"{name} must contain finite numbers")


def _rotate(point: Vec3, rotation: Vec3) -> Vec3:
    rx, ry, rz = (math.radians(value) for value in (rotation.x, rotation.y, rotation.z))
    x, y, z = point.x, point.y, point.z
    # X, then Y, then Z; documented fixed order, no quaternion dependency.
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return Vec3(x, y, z)


def cube_mesh(size: float = 1.0) -> Mesh:
    _finite((size,), "cube size")
    if size <= 0.0:
        raise Scene3DError("cube size must be positive")
    h = size / 2.0
    quads = (
        ((-h,-h,h),(h,-h,h),(h,h,h),(-h,h,h)),
        ((h,-h,-h),(-h,-h,-h),(-h,h,-h),(h,h,-h)),
        ((h,-h,h),(h,-h,-h),(h,h,-h),(h,h,h)),
        ((-h,-h,-h),(-h,-h,h),(-h,h,h),(-h,h,-h)),
        ((-h,h,h),(h,h,h),(h,h,-h),(-h,h,-h)),
        ((-h,-h,-h),(h,-h,-h),(h,-h,h),(-h,-h,h)),
    )
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    for quad in quads:
        base = len(vertices)
        vertices.extend(Vec3(*point) for point in quad)
        faces.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
    return Mesh(tuple(vertices), tuple(faces))


def sphere_mesh(radius: float = 1.0, segments: int = 16, rings: int = 8) -> Mesh:
    _finite((radius,), "sphere radius")
    if radius <= 0.0:
        raise Scene3DError("sphere radius must be positive")
    if not isinstance(segments, int) or not isinstance(rings, int) or not (3 <= segments <= 64 and 2 <= rings <= 32):
        raise Scene3DError("sphere segments must be 3–64 and rings 2–32")
    vertices = []
    for ring in range(rings + 1):
        theta = math.pi * ring / rings
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            vertices.append(Vec3(
                radius * math.sin(theta) * math.cos(phi),
                radius * math.cos(theta),
                radius * math.sin(theta) * math.sin(phi),
            ))
    faces = []
    for ring in range(rings):
        for segment in range(segments):
            a = ring * segments + segment
            b = ring * segments + (segment + 1) % segments
            c = (ring + 1) * segments + (segment + 1) % segments
            d = (ring + 1) * segments + segment
            faces.extend(((a, b, c), (a, c, d)))
    return Mesh(tuple(vertices), tuple(faces))


class Scene3D:
    def __init__(self):
        self.objects: dict[int, Object3D] = {}
        self.lights: list[PointLight] = []
        self.last_triangle_count = 0

    def _add(self, mesh: Mesh, position: Vec3, color: Color) -> int:
        if not isinstance(color, Color):
            raise Scene3DError("object material must be a colour")
        _finite((position.x, position.y, position.z), "object position")
        object_id = len(self.objects)
        self.objects[object_id] = Object3D(mesh, position, color)
        return object_id

    def cube(self, x: float, y: float, z: float, size: float, color: Color) -> int:
        return self._add(cube_mesh(size), Vec3(x, y, z), color)

    def sphere(self, x: float, y: float, z: float, radius: float, color: Color, segments: int = 16, rings: int = 8) -> int:
        return self._add(sphere_mesh(radius, segments, rings), Vec3(x, y, z), color)

    def light(self, x: float, y: float, z: float, color: Color, intensity: float = 1.0) -> None:
        _finite((x, y, z, intensity), "light")
        if intensity < 0.0 or intensity > 100.0:
            raise Scene3DError("light intensity must be between 0 and 100")
        if not isinstance(color, Color):
            raise Scene3DError("light colour must be a colour")
        if len(self.lights) >= 16:
            raise Scene3DError("a scene is limited to 16 point lights")
        self.lights.append(PointLight(Vec3(x, y, z), color, intensity))

    def rotate(self, object_id: int, x: float, y: float, z: float) -> None:
        if object_id not in self.objects:
            raise Scene3DError(f"unknown 3-D object {object_id}")
        _finite((x, y, z), "object rotation")
        self.objects[object_id].rotation = Vec3(x, y, z)

    @property
    def triangle_count(self) -> int:
        return sum(len(obj.mesh.faces) for obj in self.objects.values())

    def render(self, canvas: Canvas, yaw: float = 25.0, pitch: float = 15.0, distance: float = 6.0, fov: float = 50.0) -> None:
        if not isinstance(canvas, Canvas):
            raise Scene3DError("3-D rendering requires a canvas")
        _finite((yaw, pitch, distance, fov), "camera")
        if distance <= 0.05 or not 5.0 <= fov <= 150.0:
            raise Scene3DError("camera distance must be positive and field of view 5–150 degrees")
        scene_rotation = Vec3(pitch, yaw, 0.0)
        lights = self.lights or [PointLight(Vec3(2.0, 3.0, 4.0), Color.from_srgb(1.0, 1.0, 1.0), 1.2)]
        transformed_lights = [( _rotate(light.position, scene_rotation), light.color, light.intensity) for light in lights]
        camera = Vec3(0.0, 0.0, distance)
        focal = 0.5 * canvas.height / math.tan(math.radians(fov) / 2.0)
        depth_buffer = [math.inf] * (canvas.width * canvas.height)
        rendered = 0

        for obj in self.objects.values():
            world = [
                _rotate(_rotate(vertex, obj.rotation) + obj.position, scene_rotation)
                for vertex in obj.mesh.vertices
            ]
            for face in obj.mesh.faces:
                triangle = [world[index] for index in face]
                normal = (triangle[1] - triangle[0]).cross(triangle[2] - triangle[0]).normalized()
                if normal.dot(normal) < 0.5:
                    continue  # degenerate sphere-pole triangle
                centroid = (triangle[0] + triangle[1] + triangle[2]).scale(1.0 / 3.0)
                view = (camera - centroid).normalized()
                if normal.dot(camera - centroid) <= 0.0:
                    continue
                depths = [distance - vertex.z for vertex in triangle]
                if min(depths) <= 0.05:
                    continue  # near-plane clipping is deliberately conservative
                projected = [
                    (canvas.width / 2.0 + vertex.x * focal / depth,
                     canvas.height / 2.0 - vertex.y * focal / depth)
                    for vertex, depth in zip(triangle, depths)
                ]
                min_x = max(0, math.floor(min(point[0] for point in projected)))
                max_x = min(canvas.width - 1, math.ceil(max(point[0] for point in projected)))
                min_y = max(0, math.floor(min(point[1] for point in projected)))
                max_y = min(canvas.height - 1, math.ceil(max(point[1] for point in projected)))
                if min_x > max_x or min_y > max_y:
                    continue

                diffuse = [0.18, 0.18, 0.18]
                specular = [0.0, 0.0, 0.0]
                for position, light_color, intensity in transformed_lights:
                    offset = position - centroid
                    distance2 = max(1e-8, offset.dot(offset))
                    direction = offset.normalized()
                    attenuation = 1.0 / (1.0 + 0.04 * distance2)
                    lambert = max(0.0, normal.dot(direction)) * intensity * attenuation
                    half = (direction + view).normalized()
                    shine = max(0.0, normal.dot(half)) ** 32 * intensity * attenuation * 0.12
                    for channel, value in enumerate((light_color.r, light_color.g, light_color.b)):
                        diffuse[channel] += value * lambert
                        specular[channel] += value * shine
                material = (
                    obj.color.r * diffuse[0] + specular[0],
                    obj.color.g * diffuse[1] + specular[1],
                    obj.color.b * diffuse[2] + specular[2],
                )
                shaded = Color(material[0], material[1], material[2], obj.color.alpha)

                x0, y0 = projected[0]
                x1, y1 = projected[1]
                x2, y2 = projected[2]
                denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                if abs(denominator) < 1e-12:
                    continue
                for py in range(min_y, max_y + 1):
                    for px in range(min_x, max_x + 1):
                        sx, sy = px + 0.5, py + 0.5
                        w0 = ((y1 - y2) * (sx - x2) + (x2 - x1) * (sy - y2)) / denominator
                        w1 = ((y2 - y0) * (sx - x2) + (x0 - x2) * (sy - y2)) / denominator
                        w2 = 1.0 - w0 - w1
                        if w0 < -1e-9 or w1 < -1e-9 or w2 < -1e-9:
                            continue
                        inverse_depth = w0 / depths[0] + w1 / depths[1] + w2 / depths[2]
                        if inverse_depth <= 0.0:
                            continue
                        depth = 1.0 / inverse_depth
                        pixel = py * canvas.width + px
                        if depth >= depth_buffer[pixel]:
                            continue
                        depth_buffer[pixel] = depth
                        canvas._store(pixel * 4, shaded)
                rendered += 1
        canvas.draw_calls += 1
        self.last_triangle_count = rendered
