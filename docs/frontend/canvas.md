# Canvas and PNG

`Canvas` is a premultiplied RGBA software framebuffer with linear-light colour.

* Dimensions: 1–4096 per side, bounded by a total-pixel limit.
* Shapes: rectangles, circles and lines with 4×4 coverage anti-aliasing.
* Effects: multi-stop perceptual gradients, additive radial glow, deterministic
  procedural aurora (artistic fBm, not a physical sky model).
* Composition: source-over in premultiplied space; sampling helpers expose both
  premultiplied and straight-alpha pixels.

`png.py` writes and reads RGBA8 non-interlaced PNGs:

* original chunk framing (IHDR/IDAT/IEND), filter 0, zlib compression;
* CRC recomputation and validation;
* decompressed-size and filter checks;
* truncation (missing IEND) rejection;
* HDR tone mapping (`clip` or `aces`) at encode time.

`चित्र.प्रदर्शय(चित्रपट्ट)` hands the framebuffer to the host's attached
presentation backend (capability `दृश्य`). The canvas is not consumed or mutated, so
a program can present the same surface repeatedly after drawing each frame.

Limits: no palette/grayscale/interlaced PNG variants, no gamma chunks, no text
shaping, no GPU. Encode time is dominated by zlib and the Python loop; see
`benchmarks/reference-machine.json`.
