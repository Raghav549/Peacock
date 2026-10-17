# Colour pipeline

`peacock/frontend/colour.py` stores linear-light RGB plus alpha and converts on
demand.

* sRGB transfer functions (IEC 61966-2-1).
* XYZ (D65), CIELAB, Oklab and Oklch.
* WCAG 2.x relative luminance and contrast ratio.
* Oklab interpolation, lightening/darkening, hue rotation, complement.
* Deterministic palettes and LUT-backed gradients.
* Gamut checks/clipping; out-of-gamut values are preserved until clipping.

Verified reference values (tests): white Oklab L ≈ 1.0; sRGB red Oklab
(0.627955, 0.224863, 0.125846); white-on-black contrast 21.0;
`palette(4, 7)` = `#d473cd, #6a6300, #0065a1, #df7d7a`.

Colour is a language-level opaque type: `colour.srgb(...)`, `colour.oklab(...)`,
`colour.from_hex(...)`, properties via `Color.css`/`Color.luminance`, and `mix`.
There is no ICC profile support or spectral rendering in 0.1.
