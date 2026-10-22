"""Host policy: capability grants, resource budgets and the filesystem sandbox.

Every file operation is confined to ``root``. Paths are resolved (following
symlinks) and must remain inside the root. This is a best-effort sandbox, not a
kernel-enforced one; TOCTOU races and symlink swaps are not fully prevented. The
limitations are documented in SECURITY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from peacock.compiler.diagnostics import HostError
from peacock.compiler.tokens import KNOWN_CAPABILITIES as _LANGUAGE_CAPABILITIES
from peacock.sanskrit import surface

#: The runtime accepts exactly the capabilities the language defines.
KNOWN_CAPABILITIES = frozenset(_LANGUAGE_CAPABILITIES)


@dataclass
class HostPolicy:
    grants: frozenset[str] = frozenset()
    root: str = "."
    max_steps: int = 2_000_000
    max_call_depth: int = 128
    max_output_chars: int = 1_000_000
    max_tensor_elements: int = 1_000_000
    max_dataset_samples: int = 200_000
    max_training_epochs: int = 10_000
    max_file_bytes: int = 64 * 1024 * 1024
    #: Optional callable that receives a Canvas when a program calls
    #: ``चित्र.प्रदर्शय``. Attached by the CLI or an embedding host.
    presenter: object | None = None
    #: Optional interactive UI presenter, attached explicitly by the host.
    ui_presenter: object | None = None
    #: Optional callable (objective, max_steps) configured by an embedding host.
    #: Endpoint, model, credentials and tool registry never come from source.
    llm_runner: object | None = None
    #: Native HTTP handles are host-owned and closed even after a VM fault.
    server_handles: dict[int, object] = field(default_factory=dict, repr=False)
    next_server_handle: int = 1

    def __post_init__(self):
        unknown = self.grants - KNOWN_CAPABILITIES
        if unknown:
            raise HostError(f"unknown capability grant(s): {', '.join(sorted(unknown))}", "PE5002")
        if not isinstance(self.root, str):
            raise HostError("host root must be a string", "PE5002")
        if self.max_steps < 1 or self.max_call_depth < 1:
            raise HostError("host resource limits must be positive", "PE5002")
        root = Path(self.root)
        if not root.exists():
            raise HostError(f"host sandbox root '{self.root}' does not exist", "PE5002")
        if not root.is_dir():
            raise HostError(f"host sandbox root '{self.root}' is not a directory", "PE5002")

    def require(self, capability: str) -> None:
        if capability not in self.grants:
            raise HostError(
                f"host has not granted capability '{surface(capability)}'",
                "PE4001",
            )

    @property
    def root_path(self) -> Path:
        return Path(self.root).resolve()

    def present(self, canvas) -> None:
        """Hand a frame to the attached presentation backend.

        Requires the ``दृश्य`` grant. A granted capability without an attached
        backend is a configuration error (PE4006), not a capability denial.
        Backend failures surface as host errors so programs cannot corrupt the
        VM by raising arbitrary exceptions.
        """
        self.require("ui")
        if self.presenter is None:
            raise HostError(
                "no presentation backend is attached; run with --present DIR or attach one from an embedding host",
                "PE4006",
            )
        try:
            self.presenter(canvas)
        except HostError:
            raise
        except Exception as exc:  # pragma: no cover - defensive boundary
            raise HostError(f"presentation backend failed: {exc}", "PE5003") from exc

    def present_ui(self, ui) -> None:
        """Present a retained UI through an explicitly attached interactive host."""

        self.require("ui")
        if self.ui_presenter is None:
            raise HostError(
                "no interactive UI backend is attached; run with --ui-serve PORT or attach one from an embedding host",
                "PE4006",
            )
        try:
            self.ui_presenter(ui)
        except HostError:
            raise
        except Exception as exc:
            raise HostError(f"interactive UI backend failed: {exc}", "PE5003") from exc

    def run_autonomous_agent(self, objective: str, max_steps: int):
        """Run a host-configured LLM agent under an explicit network grant."""

        self.require("network")
        if self.llm_runner is None:
            raise HostError(
                "no LLM agent runner is configured; use --llm-url/--llm-model or attach one from an embedding host",
                "PE4006",
            )
        try:
            return self.llm_runner(objective, max_steps)
        except HostError:
            raise
        except Exception as exc:
            raise HostError(f"LLM agent runner failed: {exc}", "PE5003") from exc

    def close(self) -> None:
        """Release host-owned native server resources (idempotently)."""

        handles, self.server_handles = self.server_handles, {}
        for server in handles.values():
            try:
                server.close()
            except Exception:
                pass  # cleanup must preserve the original VM result

    def resolve_path(self, path: str, *, write: bool = False) -> Path:
        if not isinstance(path, str):
            raise HostError("path must be an अक्षरमाला", "PE5002")
        if "\x00" in path:
            raise HostError("path contains a NUL byte", "PE5002")
        if not path:
            raise HostError("path may not be empty", "PE5002")
        root = self.root_path
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve(strict=False)
        except OSError as exc:
            raise HostError(f"cannot resolve path: {exc}", "PE5002") from exc
        if resolved != root and root not in resolved.parents:
            raise HostError(
                f"path '{path}' escapes the host sandbox root '{root}'",
                "PE4002",
            )
        if write:
            try:
                resolved.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise HostError(f"cannot create parent directory: {exc}", "PE5002") from exc
        return resolved

    def read_bytes(self, path: str, limit: int | None = None) -> bytes:
        self.require("fs")
        resolved = self.resolve_path(path)
        size_limit = limit if limit is not None else self.max_file_bytes
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            raise HostError(f"cannot read '{path}': {exc}", "PE5002") from exc
        if size > size_limit:
            raise HostError(
                f"file '{path}' is {size} bytes, exceeding the {size_limit}-byte limit",
                "PE5002",
            )
        try:
            with open(resolved, "rb") as fh:
                return fh.read(size_limit + 1)
        except OSError as exc:
            raise HostError(f"cannot read '{path}': {exc}", "PE5002") from exc

    def write_bytes(self, path: str, data: bytes) -> int:
        self.require("fs")
        if len(data) > self.max_file_bytes:
            raise HostError("refusing to write a file larger than the host limit", "PE5002")
        resolved = self.resolve_path(path, write=True)
        try:
            with open(resolved, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            raise HostError(f"cannot write '{path}': {exc}", "PE5002") from exc
        return len(data)

    def create_directory(self, path: str) -> None:
        """Create a directory tree inside the granted filesystem root.

        Path resolution and the `fs` grant are checked before calling the host
        filesystem. This is still best-effort confinement: it does not eliminate
        TOCTOU races against a hostile process changing symlinks concurrently.
        """
        self.require("fs")
        resolved = self.resolve_path(path, write=True)
        try:
            resolved.mkdir(parents=True, exist_ok=True)
            if not resolved.is_dir():
                raise OSError("the path exists but is not a directory")
        except OSError as exc:
            raise HostError(f"cannot create directory '{path}': {exc}", "PE5002") from exc
