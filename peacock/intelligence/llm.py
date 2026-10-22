"""Bounded, inspectable LLM/tool orchestration with explicit host authority.

No provider, credentials, filesystem tool, shell or network location is implied.
The host constructs a provider and tool registry.  The protocol implementation is
tested locally; model quality, consciousness and AGI are not claimed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
import math
import re
import socket
import time
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class LLMError(RuntimeError):
    pass


class ToolError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list["ToolSpec"],
        *,
        model: str,
        max_tokens: int,
    ) -> LLMResponse:
        ...


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    capability: str | None = None


_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_JSON_TYPES = {
    "string": str, "integer": int, "number": (int, float), "boolean": bool,
    "object": dict, "array": list,
}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not _TOOL_NAME.fullmatch(spec.name):
            raise ToolError("tool names must match [a-z][a-z0-9_]{0,63}")
        if spec.name in self._tools:
            raise ToolError(f"tool {spec.name!r} is already registered")
        if not isinstance(spec.description, str) or not spec.description.strip() or len(spec.description) > 4096:
            raise ToolError("tool description must be non-empty and at most 4096 characters")
        if not isinstance(spec.parameters, dict) or not callable(spec.handler):
            raise ToolError("tool parameters must be a JSON-schema object and handler must be callable")
        try:
            encoded = json.dumps(spec.parameters, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"invalid tool schema: {exc}") from exc
        if len(encoded) > 65_536:
            raise ToolError("tool schema exceeds 64 KiB")
        self._tools[spec.name] = spec

    def list(self) -> list[ToolSpec]:
        return [self._tools[name] for name in sorted(self._tools)]

    def execute(self, call: ToolCall, capabilities: frozenset[str]) -> str:
        spec = self._tools.get(call.name)
        if spec is None:
            raise ToolError(f"model requested unregistered tool {call.name!r}")
        if spec.capability is not None and spec.capability not in capabilities:
            raise ToolError(f"tool {call.name!r} requires host capability {spec.capability!r}")
        arguments = call.arguments
        if not isinstance(arguments, dict):
            raise ToolError("tool arguments must be a JSON object")
        try:
            encoded_arguments = json.dumps(arguments, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"tool arguments are not finite JSON: {exc}") from exc
        if len(encoded_arguments) > 16_384:
            raise ToolError("tool arguments exceed 16384 characters")
        self._validate_schema(spec.parameters, arguments)
        started = time.perf_counter()
        try:
            result = spec.handler(arguments)
        except Exception as exc:
            raise ToolError(f"tool {call.name!r} failed: {exc}") from exc
        if time.perf_counter() - started > 30:
            # This detects slow cooperative tools; it is not advertised as a
            # preemptive timeout because Python cannot safely kill arbitrary code.
            raise ToolError(f"tool {call.name!r} exceeded the 30-second cooperative limit")
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ToolError(f"tool {call.name!r} returned a non-JSON result: {exc}") from exc

    @staticmethod
    def _validate_schema(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
        if schema.get("type", "object") != "object":
            raise ToolError("only object tool-parameter schemas are supported")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise ToolError("invalid object tool schema")
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ToolError(f"missing required tool argument(s): {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = set(arguments) - set(properties)
            if unknown:
                raise ToolError(f"unknown tool argument(s): {', '.join(sorted(unknown))}")
        for name, value in arguments.items():
            definition = properties.get(name)
            if not isinstance(definition, dict) or "type" not in definition:
                continue
            expected = _JSON_TYPES.get(definition["type"])
            if expected is None:
                raise ToolError(f"unsupported schema type {definition['type']!r}")
            if definition["type"] in {"integer", "number"} and isinstance(value, bool):
                raise ToolError(f"tool argument {name!r} must be numeric, not boolean")
            if definition["type"] == "integer" and not isinstance(value, int):
                raise ToolError(f"tool argument {name!r} must be an integer")
            if definition["type"] != "integer" and not isinstance(value, expected):
                raise ToolError(f"tool argument {name!r} does not match {definition['type']}")
            if definition["type"] == "number" and not math.isfinite(value):
                raise ToolError(f"tool argument {name!r} must be finite")
            if "enum" in definition and value not in definition["enum"]:
                raise ToolError(f"tool argument {name!r} is outside its enum")
            if isinstance(value, str) and len(value) > definition.get("maxLength", 16_384):
                raise ToolError(f"tool argument {name!r} exceeds maxLength")


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not redirect requests carrying an API key to an unvalidated endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102 - stdlib hook
        return None


class OpenAICompatibleProvider:
    """Small non-streaming chat-completions client with bounded responses.

    HTTPS is required for remote hosts.  Plain HTTP is accepted only for a
    loopback test/development server.  URL and credentials are host configuration,
    never model- or program-provided tool arguments.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_response_bytes: int = 2_000_000,
        allow_insecure_remote: bool = False,
    ):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise LLMError("LLM base URL must be an http(s) URL without userinfo")
        loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not loopback:
            try:
                loopback = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                pass
        if parsed.scheme == "http" and not loopback and not allow_insecure_remote:
            raise LLMError("plain HTTP LLM endpoints are limited to loopback; use HTTPS remotely")
        if not 0 < timeout <= 120 or not 1024 <= max_response_bytes <= 16_000_000:
            raise LLMError("invalid LLM timeout or response-byte budget")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self._opener = build_opener(_NoRedirectHandler)

    def complete(self, messages: list[dict[str, Any]], tools: list[ToolSpec], *, model: str, max_tokens: int) -> LLMResponse:
        if not model or not 1 <= max_tokens <= 32_768:
            raise LLMError("invalid model name or max_tokens")
        payload: dict[str, Any] = {
            "model": model, "messages": messages, "max_tokens": max_tokens,
            "stream": False, "temperature": 0,
        }
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters}}
                for tool in tools
            ]
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = response.read(self.max_response_bytes + 1)
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        if len(data) > self.max_response_bytes:
            raise LLMError("LLM response exceeds the configured byte budget")
        try:
            document = json.loads(data.decode("utf-8"))
            message = document["choices"][0]["message"]
            content = message.get("content") or ""
            if not isinstance(content, str):
                raise TypeError("message content must be a string or null")
            calls = []
            for raw in message.get("tool_calls") or []:
                function = raw["function"]
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                if not isinstance(arguments, dict):
                    raise TypeError("tool arguments must decode to an object")
                calls.append(ToolCall(str(raw["id"]), str(function["name"]), arguments))
            usage = {
                key: int(value) for key, value in (document.get("usage") or {}).items()
                if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and isinstance(value, (int, float))
            }
            return LLMResponse(content, calls, usage)
        except (KeyError, IndexError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise LLMError(f"invalid chat-completions response: {exc}") from exc


@dataclass(slots=True)
class AgentResult:
    status: str
    text: str
    steps: int
    trace: list[dict[str, Any]]
    usage: dict[str, int]


class AutonomousAgent:
    """A bounded LLM/tool loop; autonomy means iteration, not unlimited authority."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        *,
        model: str,
        system_prompt: str = "Answer carefully. Use only the supplied tools when needed.",
        capabilities: frozenset[str] = frozenset(),
        max_steps: int = 8,
        max_tokens_per_step: int = 2048,
        max_total_tokens: int = 32_768,
        max_total_characters: int = 200_000,
        max_tool_output_characters: int = 32_768,
    ):
        if not 1 <= max_steps <= 64 or not 1 <= max_tokens_per_step <= 32_768:
            raise ValueError("invalid agent step/token budget")
        if max_total_tokens < 1 or max_total_characters < 1 or max_tool_output_characters < 1:
            raise ValueError("invalid agent total budget")
        self.provider, self.registry, self.model = provider, registry, model
        self.system_prompt = system_prompt
        self.capabilities = capabilities
        self.max_steps, self.max_tokens_per_step = max_steps, max_tokens_per_step
        self.max_total_tokens, self.max_total_characters = max_total_tokens, max_total_characters
        self.max_tool_output_characters = max_tool_output_characters

    def run(self, objective: str) -> AgentResult:
        if not isinstance(objective, str) or not objective.strip() or len(objective) > 32_768:
            raise ValueError("agent objective must be non-empty and at most 32768 characters")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": objective.strip()},
        ]
        trace: list[dict[str, Any]] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_characters = len(self.system_prompt) + len(objective)
        for step in range(1, self.max_steps + 1):
            response = self.provider.complete(
                messages, self.registry.list(), model=self.model, max_tokens=self.max_tokens_per_step
            )
            for key in usage:
                usage[key] += max(0, int(response.usage.get(key, 0)))
            total_characters += len(response.content) + sum(len(call.name) + len(json.dumps(call.arguments)) for call in response.tool_calls)
            if usage["total_tokens"] > self.max_total_tokens or total_characters > self.max_total_characters:
                raise LLMError("LLM agent exceeded its aggregate token/character budget")
            messages.append({
                "role": "assistant", "content": response.content,
                "tool_calls": [
                    {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)}}
                    for call in response.tool_calls
                ],
            })
            if not response.tool_calls:
                if not response.content.strip():
                    raise LLMError("LLM completed without content or tool calls")
                trace.append({"step": step, "kind": "final", "text": response.content})
                return AgentResult("succeeded", response.content, step, trace, usage)
            if len(response.tool_calls) > 8:
                raise ToolError("a single LLM step requested more than 8 tools")
            for call in response.tool_calls:
                output = self.registry.execute(call, self.capabilities)
                truncated = len(output) > self.max_tool_output_characters
                if truncated:
                    output = output[: self.max_tool_output_characters] + "\n…[truncated]"
                total_characters += len(output)
                if total_characters > self.max_total_characters:
                    raise LLMError("LLM agent exceeded its aggregate token/character budget")
                trace.append({
                    "step": step, "kind": "tool", "id": call.id, "name": call.name,
                    "arguments": call.arguments, "output": output, "truncated": truncated,
                })
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": output})
        trace.append({"step": self.max_steps, "kind": "stalled"})
        return AgentResult("stalled", "", self.max_steps, trace, usage)


__all__ = [
    "AgentResult", "AutonomousAgent", "LLMError", "LLMProvider", "LLMResponse",
    "OpenAICompatibleProvider", "ToolCall", "ToolError", "ToolRegistry", "ToolSpec",
]
