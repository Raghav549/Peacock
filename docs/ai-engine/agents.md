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

This planner is deliberately separate from the LLM loop below. It is not itself
an LLM, neural reasoner, autonomous network agent or AGI.

## Bounded LLM tool agents (0.4)

`peacock/intelligence/llm.py` adds a non-streaming OpenAI-compatible
chat-completions provider and a bounded tool loop. “Autonomous” here means that
the model may iterate over explicitly registered tools for a finite number of
steps; it does **not** mean unrestricted host authority, self-modification or
general intelligence.

### Provider and tool security

* Remote endpoints require HTTPS. Plain HTTP is accepted only for a loopback
  development/test server. Redirects are not followed, so credentials are not
  forwarded to an unvalidated destination.
* The URL, model, timeout and API key are host configuration, never model tool
  arguments. `--llm-key-env NAME` reads a key without placing it in source or
  trace JSON. Never commit real keys.
* Tools are registered by the host with a JSON-object argument schema. Unknown
  tools/arguments, wrong types, non-finite numbers and excessive strings are
  rejected before the handler runs.
* Each tool may name a host capability. A tool requesting `फल` or `सञ्जाल`
  cannot run unless that grant is present. The built-in offline grammar and
  calculator tools need no grant.
* Defaults are 8 steps (native callers may request 1–64), at most 8 tool calls
  per model response, 2 MiB response bytes, per-tool output truncation, and
  aggregate token/character budgets. Tool outputs count toward the aggregate
  budget even after truncation.
* Tool execution is cooperative, not preemptible: a host-supplied handler must
  provide its own I/O timeout. There is no claim of sandboxing arbitrary Python
  handlers or hostile native code.

The default CLI registry provides only offline `sutra_lookup`, `pratyahara`,
`sandhi` and a small AST-evaluated `calculator`; the calculator does not expose
Python names, calls or imports. There are no default shell, filesystem or
network tools.

### Host-side use

```bash
export LOCAL_LLM_KEY='replace-with-your-own-secret'
./bin/peacock run examples/autonomous_agent.सूत्र --grant सञ्जाल \
  --llm-url http://127.0.0.1:8000/v1 --llm-model your-model \
  --llm-key-env LOCAL_LLM_KEY
```

The example calls `अभिकर्तृ.स्वायत्त(objective, max_steps)` and prints a record:
`[status, text, steps, trace-json]`. Surface statuses are `सिद्ध` and `स्थगित`.
The trace records tool names, validated arguments, bounded outputs, truncation
and final text; it never contains the provider API key. An embedding can instead
supply `HostPolicy(llm_runner=...)` and enforce its own provider policy.

Tests use a scripted provider and a real loopback HTTP server with Sanskrit tool
arguments/results, plus schema, grant, redirect, step and budget failure tests.
No external hosted model, model quality, multi-agent distributed system or AGI
behavior is asserted by those tests.
