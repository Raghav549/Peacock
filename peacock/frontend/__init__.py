"""PEACOCK Frontend Engine: colour science, software rendering, layout, motion.

Everything here is an original implementation. Scalar mathematical functions are
the only external boundary (``libm`` via :mod:`math`). See docs/frontend/.
"""

from .colour import Color, ColorError
from .canvas import Canvas, CanvasError

__all__ = ["Color", "ColorError", "Canvas", "CanvasError"]
