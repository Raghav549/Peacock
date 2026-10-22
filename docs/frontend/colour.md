# Colour science and advanced mixing

`peacock/frontend/colour.py` stores unbounded linear-light sRGB plus straight
alpha and converts on demand. No third-party colour library is used.

## Implemented spaces and operations

* sRGB transfer functions (IEC 61966-2-1), D65 XYZ and CIELAB;
* Oklab/Oklch conversion, interpolation, lightening, hue rotation and palettes;
* WCAG 2.x relative luminance and contrast ratio;
* CIEDE2000 colour difference through `रङ्ग.वर्णान्तर(अ, ब)`;
* chroma-reducing sRGB gamut mapping through `रङ्ग.वर्णक्षेत्रीकरण(वर्णमूल्य)`;
* deterministic LUT-backed gradients and HDR-preserving clipping only at the
  requested display boundary.

The CIEDE2000 implementation is checked against the published reference pair
`(50, 2.6772, -79.7751)` and `(50, 0, -82.7485)`, yielding `2.042459…`
(reference `2.0425`). Identity and symmetry are also tested.

## Weighted mixtures

`रङ्ग.बहुमिश्रय(वर्णावलीः, भारावली, वर्णावकाश)` accepts equally sized non-empty
lists (up to 256 colours), finite non-negative weights and a positive total.
Weights are normalized automatically.

| Space value | Semantics |
|---|---|
| `"रैखिक"` | component mixing in linear-light sRGB |
| `"ओकलैब"` | perceptual rectangular Oklab mixing |
| `"ओकएलसीएच"` | Oklch lightness/chroma with weighted circular hue mean |
| `"एसआरजीबी"` | component mixing in encoded sRGB |
| `"व्यवकलन"` | approximate subtractive/pigment mixing |

Oklch's circular mean avoids the erroneous 180° result when mixing hues around
350° and 10°. The subtractive mode applies a single-constant Kubelka–Munk curve
to three broad linear-sRGB reflectance channels. It is useful for digital art,
but is explicitly **not** a spectral, measured-paint or colourant-database
simulation.

`examples/colour_lab.सूत्र` executes weighted perceptual/subtractive mixtures,
CIEDE2000 and gamut mapping through the VM. ICC profiles, full spectral
rendering, Display-P3 conversion and measured pigment libraries remain future
work.
