"""Host presentation backends.

PEACOCK's language core is platform-neutral. A host embeds the VM and presents
frames through one of these adapters. They are deliberately small and use only
the standard library. None of them is a native mobile toolkit: Android and iOS
host shells are documented but not implemented in 0.3.
"""

from .base import Backend, Frame
from .headless import HeadlessBackend
from .server import ServerBackend
from .ui import UIWebBackend
from .web import WebBackend
from .window import NativeWindowBackend

__all__ = ["Backend", "Frame", "HeadlessBackend", "NativeWindowBackend", "ServerBackend", "UIWebBackend", "WebBackend"]
