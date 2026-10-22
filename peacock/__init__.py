"""PEACOCK AI — an AI-native programming language and computing ecosystem.

This package is the **bootstrap implementation** of PEACOCK's toolchain, written in
pure Python with no third-party dependencies. It is not the long-term implementation
strategy: see ``research/architecture-decisions.md`` (ADR-0001) for the bootstrapping
plan and the path toward a self-hosted compiler.

Public components:
    peacock.compiler  — lexer, parser, type checker, IR, optimiser, bytecode
    peacock.runtime   — the original stack virtual machine and capability sandbox
    peacock.intelligence — tensors, autodiff, neural networks, training
    peacock.frontend  — colour science, software rasteriser, layout, motion
"""

__version__ = "0.3.0"
__codename__ = "Fledgling"

#: Language version accepted by this toolchain. Independent of the toolchain version.
#: 0.3 adds native grammar, agent, UI, 3-D and advanced-colour facilities.
LANGUAGE_VERSION = "0.3"
