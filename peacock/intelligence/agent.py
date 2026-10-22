"""Bounded, deterministic production-rule agents with explicit planning.

Agents contain a string blackboard and declarative condition/action/effect rules.
Planning is uniform-cost (Dijkstra) search over complete fact states.  There are
no hidden network calls, arbitrary code execution, or claims of general
intelligence.  Hosts can inspect every planned and executed action.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import itertools
import math


class AgentError(ValueError):
    pass


def _text(value: str, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise AgentError(f"{name} must be a non-empty string")
    if len(value) > 4096:
        raise AgentError(f"{name} exceeds the 4096-character agent limit")
    return value


@dataclass(frozen=True, slots=True)
class AgentRule:
    id: int
    condition_key: str
    condition_value: str
    action: str
    effect_key: str
    effect_value: str
    priority: float
    cost: float


@dataclass(frozen=True, slots=True)
class AgentEvent:
    step: int
    rule_id: int
    action: str
    effect_key: str
    before: str | None
    after: str

    def display(self) -> str:
        return f"{self.step}: {self.action} [rule={self.rule_id}; {self.effect_key}: {self.before!r}→{self.after!r}]"


State = tuple[tuple[str, str], ...]


class Agent:
    def __init__(self, goal_key: str, goal_value: str, max_steps: int = 64):
        self.goal_key = _text(goal_key, "goal key")
        self.goal_value = _text(goal_value, "goal value", allow_empty=True)
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 1024:
            raise AgentError("agent max_steps must be between 1 and 1024")
        self.max_steps = max_steps
        self.max_states = 4096
        self.facts: dict[str, str] = {}
        self.rules: list[AgentRule] = []
        self.events: list[AgentEvent] = []
        self.status = "ready"

    def fact(self, key: str, value: str) -> None:
        self.facts[_text(key, "fact key")] = _text(value, "fact value", allow_empty=True)
        if self.status != "ready":
            self.status = "ready"
            self.events.clear()

    def get(self, key: str) -> str:
        key = _text(key, "fact key")
        if key not in self.facts:
            raise AgentError(f"agent fact '{key}' does not exist")
        return self.facts[key]

    def rule(self, condition_key: str, condition_value: str, action: str, effect_key: str, effect_value: str, priority: float = 0.0, cost: float = 1.0) -> int:
        values = (condition_key, condition_value, action, effect_key, effect_value)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise AgentError("rule conditions, actions and effects must be non-empty strings")
        if any(len(value) > 4096 for value in values):
            raise AgentError("rule text exceeds the 4096-character agent limit")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (priority, cost)):
            raise AgentError("rule priority and cost must be finite")
        if cost <= 0.0 or cost > 1e9 or abs(priority) > 1e9:
            raise AgentError("rule cost must be positive and priorities/costs are limited to 1e9")
        if len(self.rules) >= 1024:
            raise AgentError("an agent is limited to 1024 rules")
        rule = AgentRule(len(self.rules), *values, float(priority), float(cost))
        self.rules.append(rule)
        self.status = "ready"
        self.events.clear()
        return rule.id

    def _state(self, facts: dict[str, str] | None = None) -> State:
        return tuple(sorted((facts if facts is not None else self.facts).items()))

    @staticmethod
    def _facts(state: State) -> dict[str, str]:
        return dict(state)

    def _goal(self, state: State) -> bool:
        return self._facts(state).get(self.goal_key) == self.goal_value

    def _plan_rules(self) -> list[AgentRule] | None:
        initial = self._state()
        if self._goal(initial):
            return []
        counter = itertools.count()
        queue: list[tuple[float, float, int, State, tuple[AgentRule, ...]]] = [(0.0, 0.0, next(counter), initial, ())]
        # Best known (cost, cumulative salience) for each complete fact state.
        # Keeping both is essential: a cheaper path always wins, but a more
        # salient equal-cost path must not be discarded during edge relaxation.
        best: dict[State, tuple[float, float]] = {initial: (0.0, 0.0)}
        expanded = 0
        while queue:
            cost, negative_salience, _order, state, path = heapq.heappop(queue)
            salience = -negative_salience
            best_cost, best_salience = best.get(state, (math.inf, -math.inf))
            if cost > best_cost + 1e-12 or (abs(cost - best_cost) <= 1e-12 and salience < best_salience - 1e-12):
                continue
            if self._goal(state):
                return list(path)
            if len(path) >= self.max_steps:
                continue
            expanded += 1
            if expanded > self.max_states:
                raise AgentError(f"planning exceeded the {self.max_states}-state safety limit")
            facts = self._facts(state)
            for rule in self.rules:
                if facts.get(rule.condition_key) != rule.condition_value:
                    continue
                updated = dict(facts)
                updated[rule.effect_key] = rule.effect_value
                next_state = self._state(updated)
                if next_state == state:
                    continue
                next_cost = cost + rule.cost
                next_salience = salience + rule.priority
                known_cost, known_salience = best.get(next_state, (math.inf, -math.inf))
                if next_cost > known_cost + 1e-12 or (abs(next_cost - known_cost) <= 1e-12 and next_salience <= known_salience + 1e-12):
                    continue
                best[next_state] = (next_cost, next_salience)
                # Higher salience wins only equal-cost ties; insertion order
                # remains the final deterministic tie-breaker.
                heapq.heappush(queue, (next_cost, -next_salience, next(counter), next_state, (*path, rule)))
        return None

    def plan(self) -> list[str] | None:
        rules = self._plan_rules()
        return None if rules is None else [rule.action for rule in rules]

    def run(self) -> list[str]:
        rules = self._plan_rules()
        self.events.clear()
        if rules is None:
            self.status = "stalled"
            return []
        for rule in rules:
            before = self.facts.get(rule.effect_key)
            self.facts[rule.effect_key] = rule.effect_value
            self.events.append(AgentEvent(len(self.events) + 1, rule.id, rule.action, rule.effect_key, before, rule.effect_value))
        self.status = "succeeded" if self._goal(self._state()) else "stalled"
        return [event.action for event in self.events]

    def fact_lines(self) -> list[str]:
        return [f"{key}={self.facts[key]}" for key in sorted(self.facts)]

    def trace(self) -> list[str]:
        return [event.display() for event in self.events]
