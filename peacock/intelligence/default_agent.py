"""Default host-configured LLM agent with small, offline, read-only tools."""

from __future__ import annotations

import ast
import math
from typing import Callable

from peacock.vyakarana import expand, get_sutra, join

from .llm import AutonomousAgent, OpenAICompatibleProvider, ToolRegistry, ToolSpec


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object", "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


def safe_calculate(expression: str) -> str:
    """Evaluate a tiny arithmetic expression without Python eval or name access."""

    if not isinstance(expression, str) or not expression.strip() or len(expression) > 128:
        raise ValueError("calculator expression must be 1..128 characters")
    expression = expression.translate(str.maketrans("०१२३४५६७८९×÷−", "0123456789*/-"))
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 40:
        raise ValueError("calculator expression is too complex")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = +evaluate(node.operand) if isinstance(node.op, ast.UAdd) else -evaluate(node.operand)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add): value = left + right
            elif isinstance(node.op, ast.Sub): value = left - right
            elif isinstance(node.op, ast.Mult): value = left * right
            elif isinstance(node.op, ast.Div):
                if right == 0: raise ValueError("division by zero")
                value = left / right
            elif isinstance(node.op, ast.Mod):
                if right == 0: raise ValueError("remainder by zero")
                value = left % right
            else:
                if abs(left) > 1e12 or not isinstance(right, (int, float)) or abs(right) > 16:
                    raise ValueError("power operands exceed the calculator limits")
                value = left ** right
        else:
            raise ValueError("calculator accepts only numeric +, -, *, /, %, ** and parentheses")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError("calculator result exceeds finite numeric limits")
        return value

    result = evaluate(tree)
    return str(result)


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "sutra_lookup", "Read one numbered sūtra from the local attributed corpus",
        _schema({"id": {"type": "string", "maxLength": 16}}),
        lambda args: get_sutra(args["id"]).display(),
    ))
    registry.register(ToolSpec(
        "pratyahara", "Expand one Māheśvara pratyāhāra locally",
        _schema({"name": {"type": "string", "maxLength": 8}}),
        lambda args: " ".join(expand(args["name"])),
    ))
    registry.register(ToolSpec(
        "sandhi", "Apply one supported two-boundary vowel-sandhi rule; unsupported boundaries are errors",
        _schema({"left": {"type": "string", "maxLength": 256}, "right": {"type": "string", "maxLength": 256}}),
        lambda args: (lambda result: f"{result.text} — {result.rule_id} {result.rule_name}")(join(args["left"], args["right"])),
    ))
    registry.register(ToolSpec(
        "calculator", "Evaluate bounded arithmetic without names, calls, files or eval",
        _schema({"expression": {"type": "string", "maxLength": 128}}),
        lambda args: safe_calculate(args["expression"]),
    ))
    return registry


def build_llm_runner(base_url: str, model: str, api_key: str | None = None) -> Callable[[str, int], object]:
    """Construct a runner for `HostPolicy`; credentials stay in this closure."""

    provider = OpenAICompatibleProvider(base_url, api_key=api_key)
    registry = default_tool_registry()

    def run(objective: str, max_steps: int):
        agent = AutonomousAgent(
            provider, registry, model=model, max_steps=max_steps,
            system_prompt=(
                "You are a bounded PEACOCK language assistant. Use the supplied local "
                "grammar/calculator tools when they improve factual accuracy. Never invent "
                "grammar derivations. Give a concise final answer in Sanskrit when asked in Sanskrit."
            ),
        )
        return agent.run(objective)

    return run


__all__ = ["build_llm_runner", "default_tool_registry", "safe_calculate"]
