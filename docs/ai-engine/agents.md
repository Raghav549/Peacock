# Native अभिकर्तृ agents

`peacock/intelligence/agent.py` provides a bounded agent substrate based on an
inspectable string blackboard and production rules. It is usable from `.सूत्र`
without a network service or third-party agent framework.

## Model

`अभिकर्तृ.सृज(लक्ष्यसूची, लक्ष्यमूल्य, अधिकतमचरण)` returns opaque
`अभिकर्तृप्रकार`. Facts are `key=value` strings. A rule contains:

1. one exact condition (`when_key = when_value`);
2. an inspectable action label;
3. one effect (`set_key = set_value`);
4. finite salience and a positive planning cost.

`अभिकर्तृ.तथ्य`, `अभिकर्तृ.नियम`, `अभिकर्तृ.प्राप्नु` and
`अभिकर्तृ.तथ्यावली` manage and inspect this state.

## Planning and execution

`अभिकर्तृ.योजना(कर्ता)` runs Dijkstra search over complete sorted fact states.
Minimum total cost wins; cumulative salience breaks equal-cost ties and rule
insertion order is the final deterministic tie-breaker. It returns action labels,
or an empty list when no plan exists/the goal is already satisfied;
`अभिकर्तृ.स्थिति` distinguishes `सज्ज`, `सिद्ध` and `स्थगित`.

`अभिकर्तृ.चलाय(कर्ता)` executes the selected plan, applies each effect and
records step, rule ID, action and before/after value. `अभिकर्तृ.अनुसरण` exposes
that trace. Planning and execution require the `गणना` capability; declaring it
does not make the host grant it.

Safety limits are explicit: 1–1024 steps, at most 1024 rules, 4096 expanded
states, and 4096 characters per fact/rule string. Cycles cannot cause an
unbounded loop because states have best-cost records and positive edge costs.

```bash
./bin/peacock run examples/agents.सूत्र --grant गणना
# plan: द्वारं गच्छ → गृहं प्रविश
```

This is a deterministic planner/rule engine, not a general tool-use protocol,
LLM, neural reasoner, autonomous network agent or AGI. There are no hidden host
calls, arbitrary code execution, persistent distributed memory or unsupported
claims of general intelligence.
