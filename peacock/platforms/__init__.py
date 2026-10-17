"""Host presentation backends.

PEACOCK's language core is platform-neutral. A host embeds the VM and presents
frames through one of these adapters. They are deliberately small and use only
the standard library. None of them is a native mobile toolkit: Android and iOS
host shells are documented but not implemented in 0.1.
"""

from .base import Backend, Frame
from .headless import HeadlessBackend
from .server import ServerBackend
from .web import WebBackend

__all__ = ["Backend", "Frame", "HeadlessBackend", "ServerBackend", "WebBackend"]
