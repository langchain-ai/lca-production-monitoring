# Conversation Generator Setup

## Overview

The capstone uses two AI agents conversing with each other to simulate realistic customer support interactions for ACME Supply Co. (a Looney Tunes-themed catalog of cartoon products).

### The Two Agents

**CSA Agent ("Ace")** — The customer support representative. Uses `gpt-5-nano` by default (`gpt-5-mini` for scenarios marked `more_powerful_model`). Has access to two tools: a SQL database tool for querying the product catalog and customer records, and a knowledge base search tool for company policies and procedures.

**Customer Agent** — Simulates one of five Looney Tunes characters (Wile E. Coyote, Yosemite Sam, Elmer Fudd, Marvin the Martian, Sylvester Feline), each with a defined personality, query type, and task. Uses `gpt-5`. Has access to the SQL database tool to look up products before asking questions.

### How a Conversation Works

Each scenario is defined in `scenarios.tsv`. The conversation runner (`test_conversation.py`) loads the scenario, creates both agents, and runs them in a loop:

1. Customer sends an opening message
2. CSA responds
3. Customer responds
4. Loop repeats until the customer sends `TASK_COMPLETE` or the turn limit is reached
5. When `TASK_COMPLETE` is detected, the customer's final message is sent to the CSA so it appears in the CSA trace

Both agents maintain conversation history via a shared `thread_store` keyed by `thread_id`.

### Scenarios

27 scenarios are defined in `scenarios.tsv`, covering query types including product specs, orders, returns, complaints, and PII verification. Each scenario specifies the customer character, personality, number of turns, whether to reveal PII, and whether the customer should end satisfied (`satisfied` column).

---

## LangSmith Observability

### Runs, Traces, Root & Child, and Threads

**Run** — the fundamental unit in LangSmith. Every `@traceable`-decorated function call creates one run. A run records the function name, inputs, outputs, timing, and any tags, metadata, or costs you attach.

**Root run** — a run that has no parent. It's the entry point of an execution — the outermost `@traceable` call. In our code, each call to `csa.chat()` creates a root run because it's called from outside any other traceable context.

**Child run** — a run nested inside another. When `_call_llm()` is called from inside `chat()`, it creates a child run under the `chat()` root. When `query_database()` or `search_knowledge_base()` are called, they create child runs too. The full tree looks like:

```
chat()                        ← root run
├── query_database()          ← child run (tool call)
├── _call_llm()               ← child run (LLM call)
├── query_database()          ← child run (tool call, if called again)
└── _call_llm()               ← child run (LLM call, final response)
```

**Trace** — the complete tree of runs from a single root run downward. The trace ID equals the root run's ID. When you view a trace in LangSmith, you see the root run and all its children laid out as a hierarchy. In our setup, each call to `csa.chat()` produces one trace.

**Thread** — groups multiple traces from the same multi-turn conversation together. Since a CSA conversation has many turns, each turn produces its own trace. The `thread_id` links all those traces into a single thread so you can see the full conversation flow in one view in LangSmith. Each agent (CSA and customer) gets its own `thread_id`, so they appear as separate threads.

A 4-turn CSA conversation produces:
- 4 traces (one per `csa.chat()` call)
- Each trace has multiple child runs (tool calls + LLM calls)
- All 4 traces are linked to the same CSA thread

---

Every agent turn is traced in LangSmith. Three types of information are attached to traces:

### Tags
Simple string labels, filterable in the LangSmith UI.

| Tag | Example | Purpose |
|---|---|---|
| Customer name | `"Elmer Fudd"` | Filter by customer |
| Scenario number | `"scenario:10"` | Filter by scenario |
| Agent role | `"csa"` or `"customer"` | Filter CSA vs customer traces |

### Metadata
Key/value pairs attached to each trace, visible in LangSmith UI.

| Key | Example Value | Purpose |
|---|---|---|
| `run_id` | `"637112c0-..."` | Identifies the batch of 27 scenarios |
| `session_id` | `"a1b2c3-..."` | Identifies one conversation |
| `scenario` | `10` | Scenario number |
| `customer_name` | `"Elmer Fudd"` | Customer full name |
| `agent_name` | `"csa"` | Which agent produced this trace |

### Feedback
A separate LangSmith object linked to a run by its run ID. Used for thumbs up/down scoring based on whether the customer was expected to end satisfied.

| Key | Score | Meaning |
|---|---|---|
| `thumbs_up_down` | `1` | Customer satisfied |
| `thumbs_up_down` | `0` | Customer not satisfied |

---

## Code Examples

### Defining tags and metadata (`test_conversation.py:78-81`)

```python
base_meta = {"run_id": run_id, "session_id": conversation_id, "scenario": scenario["number"], "customer_name": customer_name}
base_tags = [customer_name, f"scenario:{scenario['number']}"]
csa_extra = {"langsmith_extra": {"metadata": {**base_meta, "agent_name": "csa"}, "tags": [*base_tags, "csa"]}}
customer_extra = {"langsmith_extra": {"metadata": {**base_meta, "agent_name": "customer"}, "tags": [*base_tags, "customer"]}}
```

Tags and metadata are bundled into a `langsmith_extra` dict. The `@traceable` decorator on `Agent.chat()` intercepts this kwarg and applies it to the trace before calling the underlying function.

### Passing tags and metadata at call time (`test_conversation.py:96`)

```python
csa_result = await csa.chat(customer_message, **csa_extra)
```

`langsmith_extra` is passed as a kwarg. The `@traceable` wrapper intercepts it, uses it to configure the trace, and then passes it along to `chat()` where it is received but ignored.

### Receiving `langsmith_extra` in the decorated function (`agent.py:49-50`)

```python
@traceable(name="Agent")
async def chat(self, question: str, langsmith_extra: dict | None = None) -> dict:
```

`langsmith_extra` is declared explicitly in the signature for clarity, though `@traceable` would consume it silently even without the declaration.

### Adding feedback after the conversation (`test_conversation.py`)

```python
satisfied = scenario.get("satisfied", "").upper() == "TRUE"
score = 1 if satisfied else 0
ls_client = Client()
for rid in csa_run_ids:
    ls_client.create_feedback(run_id=rid, key="thumbs_up_down", score=score)
```

After the conversation loop ends, `create_feedback()` is called once per CSA turn, linking the thumbs up/down score to each CSA trace for that conversation.

### Using `get_current_run_tree()`

`get_current_run_tree()` returns the active LangSmith run from the current thread context — no client instantiation needed. It is available inside any function decorated with `@traceable`, or any function called from one. There are three distinct patterns in this codebase:

**1. Capture the run ID to use later (`agent.py:52-53`)**

```python
run = get_current_run_tree()
run_id = str(run.id) if run else None
```

The run ID is returned from `chat()` and later passed to `create_feedback()` to attach thumbs up/down scoring to the trace.

**2. Set model metadata so LangSmith can compute costs (`agent.py:36-45`)**

```python
run = get_current_run_tree()
if run:
    run.extra = {
        **(run.extra or {}),
        "metadata": {
            **(run.extra or {}).get("metadata", {}),
            "ls_provider": "openai",
            "ls_model_name": self.model,
        },
    }
```

LangSmith computes token costs server-side from the model name and token counts. Without `ls_provider` and `ls_model_name` in `run.extra`, costs won't appear in the monitoring dashboard.

**3. Add a fixed cost to a tool run (`database_tool.py:39-41`)**

```python
run = get_current_run_tree()
if run:
    run.set(usage_metadata={"total_cost": 0.0007})
```

Tool calls don't have token usage, but you can still assign a cost manually. Here each database query is given a fixed cost of $0.0007 to simulate a real API call cost.
