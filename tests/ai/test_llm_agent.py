import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from peacock.compiler.diagnostics import CapabilityError, HostError
from peacock.intelligence.default_agent import default_tool_registry, safe_calculate
from peacock.intelligence.llm import (
    AgentResult,
    AutonomousAgent,
    LLMError,
    LLMResponse,
    OpenAICompatibleProvider,
    ToolCall,
    ToolError,
    ToolRegistry,
    ToolSpec,
)
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM
from peacock.vyakarana import get_sutra
from tests.support import compile_ok, run_source


class ScriptedProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, messages, tools, *, model, max_tokens):
        self.requests.append((list(messages), list(tools), model, max_tokens))
        if not self.responses:
            raise AssertionError("provider called beyond script")
        return self.responses.pop(0)


def schema(properties, required=None):
    return {
        "type": "object", "properties": properties,
        "required": required or list(properties), "additionalProperties": False,
    }


class ToolAgentTests(unittest.TestCase):
    def test_tool_loop_schema_capabilities_and_final_result(self):
        provider = ScriptedProvider([
            LLMResponse(tool_calls=[ToolCall("call-1", "add", {"a": 2, "b": 3})], usage={"total_tokens": 12}),
            LLMResponse("५", usage={"total_tokens": 4}),
        ])
        registry = ToolRegistry()
        registry.register(ToolSpec(
            "add", "Add two integers", schema({"a": {"type": "integer"}, "b": {"type": "integer"}}),
            lambda args: args["a"] + args["b"], capability="compute",
        ))
        agent = AutonomousAgent(provider, registry, model="test", capabilities=frozenset({"compute"}))
        result = agent.run("२ + ३")
        self.assertEqual((result.status, result.text, result.steps), ("succeeded", "५", 2))
        self.assertEqual(result.trace[0]["output"], "5")
        self.assertEqual(result.usage["total_tokens"], 16)
        tool_messages = [m for m in provider.requests[1][0] if m["role"] == "tool"]
        self.assertEqual(tool_messages[0]["content"], "5")

    def test_unregistered_capability_and_schema_errors_are_not_executed(self):
        calls = []
        registry = ToolRegistry()
        registry.register(ToolSpec("add", "Add", schema({"a": {"type": "integer"}}), lambda args: calls.append(args), "compute"))
        with self.assertRaisesRegex(ToolError, "requires host capability"):
            registry.execute(ToolCall("1", "add", {"a": 1}), frozenset())
        with self.assertRaisesRegex(ToolError, "unknown tool argument"):
            registry.execute(ToolCall("1", "add", {"a": 1, "extra": 2}), frozenset({"compute"}))
        with self.assertRaisesRegex(ToolError, "unregistered"):
            registry.execute(ToolCall("1", "missing", {}), frozenset({"compute"}))
        self.assertEqual(calls, [])

    def test_step_limit_and_tool_output_bound(self):
        provider = ScriptedProvider([
            LLMResponse(tool_calls=[ToolCall(str(i), "large", {})]) for i in range(3)
        ])
        registry = ToolRegistry()
        registry.register(ToolSpec("large", "Large output", schema({}), lambda _args: "x" * 100))
        agent = AutonomousAgent(
            provider, registry, model="test", max_steps=3, max_tool_output_characters=20,
        )
        result = agent.run("loop")
        self.assertEqual(result.status, "stalled")
        self.assertEqual(result.steps, 3)
        self.assertTrue(all(row["truncated"] for row in result.trace if row["kind"] == "tool"))
        self.assertLessEqual(max(len(row["output"]) for row in result.trace if row["kind"] == "tool"), 35)

    def test_tool_output_counts_toward_aggregate_budget(self):
        provider = ScriptedProvider([
            LLMResponse(tool_calls=[ToolCall("1", "large", {})]),
            LLMResponse("must not be requested"),
        ])
        registry = ToolRegistry()
        registry.register(ToolSpec("large", "Large output", schema({}), lambda _args: "x" * 100))
        agent = AutonomousAgent(
            provider, registry, model="test", system_prompt="", max_total_characters=30,
            max_tool_output_characters=20,
        )
        with self.assertRaisesRegex(LLMError, "aggregate"):
            agent.run("loop")
        self.assertEqual(len(provider.requests), 1)

    def test_remote_plain_http_is_rejected(self):
        with self.assertRaisesRegex(LLMError, "loopback"):
            OpenAICompatibleProvider("http://example.com/v1")


class LocalChatCompletionTests(unittest.TestCase):
    def test_real_http_provider_executes_sanskrit_tool_and_returns_answer(self):
        requests = []
        responses = [
            {
                "choices": [{"message": {
                    "role": "assistant", "content": "",
                    "tool_calls": [{"id": "grammar-1", "type": "function", "function": {
                        "name": "sutra_lookup", "arguments": json.dumps({"id": "1.1.1"}),
                    }}],
                }}],
                "usage": {"total_tokens": 20},
            },
            {
                "choices": [{"message": {"role": "assistant", "content": "1.1.1 वृद्धिरादैच्", "tool_calls": []}}],
                "usage": {"total_tokens": 8},
            },
        ]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                requests.append({
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "payload": json.loads(self.rfile.read(length)),
                })
                body = json.dumps(responses[len(requests) - 1], ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = OpenAICompatibleProvider(
                f"http://127.0.0.1:{server.server_address[1]}/v1", api_key="test-secret",
            )
            registry = ToolRegistry()
            registry.register(ToolSpec(
                "sutra_lookup", "Read one local Aṣṭādhyāyī sūtra",
                schema({"id": {"type": "string", "maxLength": 16}}),
                lambda args: get_sutra(args["id"]).display(),
            ))
            result = AutonomousAgent(provider, registry, model="local-test", max_steps=3).run("सूत्रं 1.1.1 किम्?")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.text, "1.1.1 वृद्धिरादैच्")
            self.assertEqual(result.trace[0]["output"], "1.1.1 वृद्धिरादैच्")
            self.assertEqual(len(requests), 2)
            self.assertTrue(all(row["path"] == "/v1/chat/completions" for row in requests))
            self.assertTrue(all(row["authorization"] == "Bearer test-secret" for row in requests))
            self.assertEqual(requests[0]["payload"]["tools"][0]["function"]["name"], "sutra_lookup")
            tool_messages = [m for m in requests[1]["payload"]["messages"] if m["role"] == "tool"]
            self.assertEqual(tool_messages[0]["content"], "1.1.1 वृद्धिरादैच्")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_redirect_is_rejected_without_following_it(self):
        redirected = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", "/redirected")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):
                redirected.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = OpenAICompatibleProvider(
                f"http://127.0.0.1:{server.server_address[1]}/v1", api_key="do-not-forward",
            )
            with self.assertRaisesRegex(LLMError, "request failed"):
                provider.complete([], [], model="test", max_tokens=10)
            self.assertEqual(redirected, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


class DefaultAgentToolTests(unittest.TestCase):
    def test_sanskrit_arithmetic_and_safe_registry(self):
        self.assertEqual(safe_calculate("२ + ३ × ४"), "14")
        self.assertEqual(safe_calculate("१० ÷ ४"), "2.5")
        self.assertEqual(
            {spec.name for spec in default_tool_registry().list()},
            {"sutra_lookup", "pratyahara", "sandhi", "calculator"},
        )

    def test_calculator_rejects_names_calls_and_invalid_math(self):
        for expression in ('__import__("os")', "open('x')", "1 / 0", "2 ** 10000"):
            with self.subTest(expression=expression), self.assertRaises((ValueError, SyntaxError, OverflowError)):
                safe_calculate(expression)


class NativeAutonomousAgentTests(unittest.TestCase):
    SOURCE = """
    उपयोग अभिकर्तृ
    कार्य मुख्य() -> एकक {
        अधिकार सञ्जाल;
        स्थापय परिणाम = अभिकर्तृ.स्वायत्त("सूत्रं 1.1.1", २);
        निश्चिनु परिणाम[०] == "सिद्ध";
        निश्चिनु परिणाम[२] == "1";
        मुद्रय(परिणाम[१]);
        मुद्रय(परिणाम[३]);
    }
    """

    def test_native_host_runner_and_sanskrit_result(self):
        calls = []

        def runner(objective, max_steps):
            calls.append((objective, max_steps))
            return AgentResult("succeeded", "1.1.1 वृद्धिरादैच्", 1, [{"kind": "tool", "name": "sutra_lookup"}], {})

        image = compile_ok(self.SOURCE).image
        output = io.StringIO()
        host = HostPolicy(grants=frozenset({"network"}), llm_runner=runner)
        VM(image, host, stdout=output).run()
        self.assertEqual(calls, [("सूत्रं 1.1.1", 2)])
        self.assertIn("1.1.1 वृद्धिरादैच्\n", output.getvalue())
        self.assertIn('"name": "sutra_lookup"', output.getvalue())

    def test_native_network_grant_and_runner_are_required(self):
        with self.assertRaises(CapabilityError):
            run_source(self.SOURCE)
        with self.assertRaises(HostError) as caught:
            run_source(self.SOURCE, grants=("network",))
        self.assertEqual(caught.exception.code, "PE4006")
        self.assertIn("no LLM agent runner", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
