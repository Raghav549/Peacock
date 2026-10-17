# Motion, layout and physics

* **Easing:** named curves plus a CSS-style cubic Bézier solver with Newton
  iterations; inputs clamped to [0, 1]; unknown names are errors.
* **Springs:** damped harmonic oscillator with explicit substeps (max 1/240 s);
  deterministic; returns samples and supports settle checks.
* **Timelines:** sorted keyframes, numeric or Color interpolation, optional loop,
  easing attached to the destination keyframe (CSS semantics).
* **Layout:** row/column stacks with grow factors, min sizes, padding, gaps,
  origin offsets and overflow reporting. Not a full constraint solver.
* **Physics:** 2-D axis-aligned rigid bodies, fixed 1/120 s substeps, gravity,
  restitution, friction, positional correction and static bodies. No rotation,
  joints or broadphase.

All four are deterministic and dependency-free. They are libraries, not an
animation runtime: there is no scheduler, frame clock, input loop or GPU
compositor yet.
