# Native त्रिअयाम software renderer

`peacock/frontend/scene3d.py` implements real CPU triangle rendering. It does
not wrap a GPU library and does not relabel a 2-D effect as 3-D.

## Geometry and scene API

`त्रिअयाम.सृज()` returns opaque `त्रिअयामदृश्य`.

| Native | Implemented operation |
|---|---|
| `त्रिअयाम.घन(...)` | 24 vertices/12 triangles, position, size and material |
| `त्रिअयाम.गोलक(...)` | bounded UV sphere: 3–64 segments, 2–32 rings |
| `त्रिअयाम.भ्रमय(...)` | object Euler rotation in X→Y→Z order |
| `त्रिअयाम.प्रकाश(...)` | up to 16 coloured point lights |
| `त्रिअयाम.त्रिभुजसंख्या(...)` | total mesh triangle count |
| `त्रिअयाम.अङ्कन(...)` | render into an existing `चित्रपट` |

The renderer applies object and scene rotations, perspective projection, a
positive near-plane check, back-face culling and perspective-correct reciprocal
depth interpolation. A per-pixel depth buffer resolves occlusion independently
of object insertion order.

## Lighting and colour

Materials use the existing linear-light `वर्ण` values. Each visible triangle
receives ambient light, coloured Lambertian diffuse illumination with distance
attenuation, and a bounded Blinn–Phong specular term. HDR values remain linear
until the canvas/PNG display transform. Flat triangle normals intentionally
produce faceted sphere shading; smooth vertex-normal interpolation is not yet
claimed.

```bash
./bin/peacock run examples/scene3d.सूत्र --grant सञ्चय --root .
# writes a real 320×200 examples/out/scene3d.png with 588 mesh triangles
```

Tests render actual pixels, verify a nearer red cube occludes a distant blue
cube, exercise sphere lighting and reject invalid meshes, cameras and excess
lights. The implementation is single-threaded CPU software rendering; GPU
compute, ray tracing, texture mapping, smooth shading, glTF and native window
integration remain unimplemented.
