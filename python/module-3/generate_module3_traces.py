"""Generate ~200 synthetic ACME support traces for an A/B test (Module 3 lab).

Each trace is part of a multi-turn conversation **thread** (2-4 turns).
Traces in the same thread share a `thread_id` in `extra.metadata`.

Version A: reliable baseline -- no tool errors, normal latency, happy endings.
Version B: error-prone -- ~40% of tool calls fail, retries spike latency,
           conversations end with frustrated users.

Output: module3_traces.json (flat list of runs consumable by upload_traces.py)
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_NAME = "gpt-4o-mini"
SEED = 42

# ---------------------------------------------------------------------------
# Conversation templates
# ---------------------------------------------------------------------------
# Each topic: (opening question, response, tool_name or None)
# Kept intentionally smaller than module 2 since Insights isn't the focus.

TOPICS: list[tuple[str, str, str | None]] = [
    # --- Anvils ---
    (
        "When will my anvil order {order_id} arrive?",
        "Let me check order {order_id}. Your {weight} anvil is in transit and should arrive in {city}, {state} within 3-5 business days.",
        "lookup_order",
    ),
    (
        "My {weight} anvil cracked after two months. Is this covered under warranty?",
        "ACME anvils come with a 5-year structural warranty. A crack after two months is definitely covered. I'll initiate a warranty claim and send a replacement.",
        "query_product_database",
    ),
    (
        "What sizes do your anvils come in?",
        "ACME anvils are available in 50 lb, 100 lb, 200 lb, 500 lb, and 1000 lb, plus our industrial 1-ton variant. The 100 lb is our most popular.",
        "query_product_database",
    ),
    (
        "I need 50 anvils for our workshop. Do you offer bulk discounts?",
        "For orders of 50 units we offer 15% off list price. For 100+ the discount goes to 20%. I can prepare a custom quote. What size do you need?",
        None,
    ),
    (
        "What safety precautions should I take when using a {weight} anvil?",
        "Always mount it on a stable, level surface at knuckle height. Wear safety glasses, hearing protection, and steel-toed boots. Keep a 3-foot clear zone during use.",
        "search_knowledge_base",
    ),
    # --- Rocket Skates ---
    (
        "How do I adjust the speed settings on my Rocket Skates?",
        "Rocket Skates have five speed modes. Use the dial on the right skate to cycle through them. Start in Cruise mode until you're comfortable.",
        "search_knowledge_base",
    ),
    (
        "My Rocket Skates won't charge. The LED stays red.",
        "A persistent red LED usually means a battery temperature issue. Let the skates cool for 30 minutes and try again. If it persists, the charging port may need cleaning.",
        None,
    ),
    (
        "I want to return my Rocket Skates. Order {order_id}.",
        "Rocket Skates can be returned within 30 days for a full refund in original condition. Let me look up order {order_id}.",
        "lookup_order",
    ),
    # --- Giant Magnets ---
    (
        "What strength ratings are available for ACME Giant Magnets?",
        "We offer five ratings: 500, 1000, 2500, 5000, and 10000 gauss. The 1000 gauss model is our most popular for general use.",
        "query_product_database",
    ),
    (
        "Is it safe to use a {magnet_strength} magnet near electronics?",
        "We recommend keeping the {magnet_strength} model at least 3 feet from sensitive electronics. Hard drives and credit cards are especially vulnerable.",
        "search_knowledge_base",
    ),
    # --- Portable Holes ---
    (
        "How do I install a {hole_size} Portable Hole?",
        "Place the Portable Hole on any flat surface and press firmly around the edges. It adheres in about 10 seconds. Make sure the surface is clean and dry first.",
        "search_knowledge_base",
    ),
    (
        "Can I reuse a Portable Hole after removing it?",
        "Yes, Portable Holes are fully reusable. Peel from one edge slowly to avoid tearing. They maintain adhesion for up to 50 applications.",
        None,
    ),
    # --- Earthquake Pills ---
    (
        "What's the effective radius of a {quake_rating} Earthquake Pill?",
        "A {quake_rating} pill has an effective radius of about 500 feet. Effects diminish with distance. Always clear the area before activation.",
        "query_product_database",
    ),
    (
        "Are Earthquake Pills safe for indoor use?",
        "We do NOT recommend indoor use. Even our lowest-rated pills can cause structural damage in enclosed spaces. Outdoor use only, with a 500-foot clearance.",
        "search_knowledge_base",
    ),
]

# Follow-up templates (question, response, tool_name or None)
# Most followups include tool calls so Version B has enough surface area for errors.
FOLLOWUPS: list[tuple[str, str, str | None]] = [
    (
        "Can you check the status of that for me?",
        "I've looked into it and everything is on track. You should see an update within 24 hours.",
        "lookup_order",
    ),
    (
        "How long will that take?",
        "Let me check the timeline. Typically 3-5 business days. I can flag it for priority handling if you need it sooner.",
        "lookup_order",
    ),
    (
        "Is there a way to speed that up?",
        "I can escalate this to our priority team. That usually cuts the turnaround time in half.",
        "lookup_order",
    ),
    (
        "What if the problem happens again?",
        "Let me pull up your history. If it recurs, contact us and we'll fast-track a resolution. I'll add a note to your account.",
        "lookup_order",
    ),
    (
        "Can I get a refund instead?",
        "I can process a refund if you prefer. It will appear on your original payment method within 5-7 business days.",
        "lookup_order",
    ),
    (
        "Do you have any documentation on that?",
        "Yes, I'll send you a link to the relevant support article. It covers the topic in detail with step-by-step instructions.",
        "search_knowledge_base",
    ),
    (
        "Can you double-check that information?",
        "Let me verify that for you. Yes, everything checks out. The information I provided is correct.",
        "query_product_database",
    ),
    (
        "What are the next steps?",
        "Let me look up the process. You'll receive a confirmation email shortly with the details and tracking information.",
        "lookup_order",
    ),
]

# Positive closing messages (Version A threads)
POSITIVE_CLOSINGS: list[str] = [
    "Thanks, that helps!",
    "Great, got it. Appreciate the quick response.",
    "Perfect, that's exactly what I needed.",
    "Awesome, thanks for looking into that.",
    "That makes sense. Thanks!",
    "Wonderful, I'll keep an eye out for the email.",
    "Thanks so much for the help!",
    "Great, I think we're all set then.",
    "That clears things up. Thanks for your time.",
    "Excellent, you've been really helpful.",
]

POSITIVE_CLOSING_RESPONSES: list[str] = [
    "You're welcome! Don't hesitate to reach out if you need anything else.",
    "Happy to help! Have a great day.",
    "Glad I could help! Let us know if anything else comes up.",
    "Anytime! We're here if you need us.",
    "You're welcome! Enjoy the rest of your day.",
]

# Frustrated closing messages (Version B threads)
FRUSTRATED_CLOSINGS: list[str] = [
    "This is taking forever. I'll just call instead.",
    "Still not working. I'm going to try a different company.",
    "This has been really frustrating. I expected better.",
    "I've been waiting way too long for this. Not happy.",
    "Forget it, I'll figure it out myself.",
    "This whole experience has been a mess.",
    "I don't have time for this. Please escalate immediately.",
    "You know what, just cancel my order entirely.",
    "I've had nothing but problems with this. Very disappointed.",
    "I'll leave a review about this experience.",
]

FRUSTRATED_CLOSING_RESPONSES: list[str] = [
    "I'm sorry for the inconvenience. Let me see what I can do to make this right.",
    "I completely understand your frustration. I'll escalate this to our priority team right away.",
    "I apologize for the experience. I've flagged your account for immediate follow-up.",
    "I'm sorry this hasn't been smoother. I'll personally make sure this gets resolved.",
    "I understand, and I'm sorry. Let me connect you with a senior specialist who can help.",
]

# Tool error messages (Version B)
TOOL_ERRORS: list[str] = [
    "Connection timeout: upstream service did not respond within 30s",
    "Service temporarily unavailable (HTTP 503)",
    "Internal server error: database connection pool exhausted",
    "Request failed: connection reset by peer",
    "Gateway timeout: backend service unreachable",
    "Service overloaded: retry after 5 seconds",
]

# ---------------------------------------------------------------------------
# Shared random-variable pools (from module 2)
# ---------------------------------------------------------------------------
ORDER_PREFIX = "ACME"
STATES = [
    "California", "Texas", "New York", "Florida", "Illinois", "Ohio",
    "Georgia", "Pennsylvania", "North Carolina", "Michigan",
]
CITIES = [
    "Phoenix", "Austin", "Denver", "Seattle", "Portland", "Miami",
    "Chicago", "Atlanta", "Nashville", "San Diego",
]
ANVIL_WEIGHTS = ["50 lb", "100 lb", "200 lb", "500 lb", "1000 lb"]
MAGNET_STRENGTHS = ["500 gauss", "1000 gauss", "2500 gauss", "5000 gauss"]
HOLE_SIZES = ["3 ft", "5 ft", "8 ft", "10 ft"]
QUAKE_RATINGS = ["3.0", "4.5", "5.0", "6.5", "7.0"]


def _order_id() -> str:
    return f"{ORDER_PREFIX}-{random.randint(100000, 999999)}"


def _fill(template: str) -> str:
    """Replace placeholders in a template string."""
    replacements = {
        "{order_id}": _order_id(),
        "{name}": f"Customer-{random.randint(1000, 9999)}",
        "{state}": random.choice(STATES),
        "{city}": random.choice(CITIES),
        "{weight}": random.choice(ANVIL_WEIGHTS),
        "{magnet_strength}": random.choice(MAGNET_STRENGTHS),
        "{hole_size}": random.choice(HOLE_SIZES),
        "{quake_rating}": random.choice(QUAKE_RATINGS),
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


# ---------------------------------------------------------------------------
# Tool helpers
# ---------------------------------------------------------------------------
TOOL_ARGS: dict[str, callable] = {
    "lookup_order": lambda: {"order_id": _order_id()},
    "query_product_database": lambda: {"query": "product specifications"},
    "search_knowledge_base": lambda: {"query": "usage guidelines"},
}

TOOL_OUTPUTS: dict[str, callable] = {
    "lookup_order": lambda args: {
        "output": json.dumps({
            "order_id": args.get("order_id", _order_id()),
            "status": random.choice(["shipped", "processing", "delivered", "in_transit"]),
            "estimated_delivery": (
                datetime.now(timezone.utc) + timedelta(days=random.randint(1, 7))
            ).isoformat(),
        })
    },
    "query_product_database": lambda args: {
        "output": json.dumps({
            "results_count": random.randint(1, 5),
            "source": "acme_product_catalog",
        })
    },
    "search_knowledge_base": lambda args: {
        "output": json.dumps({
            "results_count": random.randint(1, 8),
            "source": "acme_knowledge_base",
        })
    },
}


def _tool_call_obj(tool_name: str, arguments: dict) -> dict:
    return {
        "id": f"call_{uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {"name": tool_name, "arguments": json.dumps(arguments)},
    }


# ---------------------------------------------------------------------------
# LLM message helpers
# ---------------------------------------------------------------------------
SYSTEM_MSG = {
    "role": "system",
    "content": (
        "You are a helpful customer support agent for ACME Industries. "
        "Answer questions about our products: Anvils, Rocket Skates, "
        "Giant Magnets, Portable Holes, and Earthquake Pills."
    ),
}


def _llm_input_messages(question: str) -> dict:
    return {
        "messages": [SYSTEM_MSG, {"role": "user", "content": question}],
    }


def _llm_output_messages(response: str, tool_calls: list[dict] | None = None) -> dict:
    msg: dict = {"role": "assistant", "content": response}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "choices": [
            {
                "index": 0,
                "message": msg,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ]
    }


# ---------------------------------------------------------------------------
# Single-trace builder
# ---------------------------------------------------------------------------
def build_trace(
    question: str,
    response: str,
    tool_name: str | None,
    base_time: datetime,
    app_version: str,
    thread_id: str,
    tool_should_error: bool = False,
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    """Build one trace (root chain + child LLM + optional tool runs).

    conversation_history: accumulated messages from prior turns in the thread.
    The root run's outputs.messages will include the full history plus this turn.
    """
    trace_id = str(uuid.uuid4())
    root_id = str(uuid.uuid4())
    llm_id = str(uuid.uuid4())

    root_start = base_time
    llm_start = root_start + timedelta(milliseconds=random.randint(5, 30))

    metadata = {"app_version": app_version, "thread_id": thread_id}
    tags = [f"version:{app_version}"]
    runs: list[dict] = []

    include_tool = tool_name is not None

    if include_tool:
        tool_id = str(uuid.uuid4())
        tool_args = TOOL_ARGS[tool_name]()
        tc_obj = _tool_call_obj(tool_name, tool_args)

        llm_end_1 = llm_start + timedelta(milliseconds=random.randint(300, 800))
        tool_start = llm_end_1 + timedelta(milliseconds=random.randint(5, 20))

        if tool_should_error:
            # Tool fails
            error_msg = random.choice(TOOL_ERRORS)
            tool_end = tool_start + timedelta(milliseconds=random.randint(2000, 5000))

            # Failed tool run
            runs.append({
                "id": tool_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": tool_name,
                "run_type": "tool",
                "inputs": tool_args,
                "outputs": None,
                "error": error_msg,
                "extra": {"metadata": metadata},
                "tags": tags,
                "start_time": tool_start.isoformat(),
                "end_time": tool_end.isoformat(),
            })

            # LLM run 1 (tool-calling, leads to error)
            runs.append({
                "id": llm_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages("", [tc_obj]),
                "error": None,
                "extra": {"metadata": {**metadata, "ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": llm_start.isoformat(),
                "end_time": llm_end_1.isoformat(),
            })

            # Retry: second LLM call to decide to retry
            retry_llm_id = str(uuid.uuid4())
            retry_llm_start = tool_end + timedelta(milliseconds=random.randint(50, 200))
            retry_llm_end = retry_llm_start + timedelta(milliseconds=random.randint(300, 600))

            retry_tc_obj = _tool_call_obj(tool_name, tool_args)

            runs.append({
                "id": retry_llm_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages("", [retry_tc_obj]),
                "error": None,
                "extra": {"metadata": {**metadata, "ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": retry_llm_start.isoformat(),
                "end_time": retry_llm_end.isoformat(),
            })

            # Retry tool call (succeeds)
            retry_tool_id = str(uuid.uuid4())
            retry_tool_start = retry_llm_end + timedelta(milliseconds=random.randint(5, 20))
            retry_tool_end = retry_tool_start + timedelta(milliseconds=random.randint(50, 300))
            tool_output = TOOL_OUTPUTS[tool_name](tool_args)

            runs.append({
                "id": retry_tool_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": tool_name,
                "run_type": "tool",
                "inputs": tool_args,
                "outputs": tool_output,
                "error": None,
                "extra": {"metadata": metadata},
                "tags": tags,
                "start_time": retry_tool_start.isoformat(),
                "end_time": retry_tool_end.isoformat(),
            })

            # Final LLM response after retry
            final_llm_id = str(uuid.uuid4())
            final_llm_start = retry_tool_end + timedelta(milliseconds=random.randint(5, 20))
            final_llm_end = final_llm_start + timedelta(milliseconds=random.randint(400, 1200))
            root_end = final_llm_end + timedelta(milliseconds=random.randint(5, 30))

            runs.append({
                "id": final_llm_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages(response),
                "error": None,
                "extra": {"metadata": {**metadata, "ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": final_llm_start.isoformat(),
                "end_time": final_llm_end.isoformat(),
            })
        else:
            # Tool succeeds (normal path)
            tool_end = tool_start + timedelta(milliseconds=random.randint(50, 300))
            tool_output = TOOL_OUTPUTS[tool_name](tool_args)

            # LLM run 1 (tool-calling)
            runs.append({
                "id": llm_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages("", [tc_obj]),
                "error": None,
                "extra": {"metadata": {**metadata, "ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": llm_start.isoformat(),
                "end_time": llm_end_1.isoformat(),
            })

            # Tool run
            runs.append({
                "id": tool_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": tool_name,
                "run_type": "tool",
                "inputs": tool_args,
                "outputs": tool_output,
                "error": None,
                "extra": {"metadata": metadata},
                "tags": tags,
                "start_time": tool_start.isoformat(),
                "end_time": tool_end.isoformat(),
            })

            # LLM run 2 (final answer)
            llm2_id = str(uuid.uuid4())
            llm2_start = tool_end + timedelta(milliseconds=random.randint(5, 20))
            llm2_end = llm2_start + timedelta(milliseconds=random.randint(400, 1200))
            root_end = llm2_end + timedelta(milliseconds=random.randint(5, 30))

            runs.append({
                "id": llm2_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages(response),
                "error": None,
                "extra": {"metadata": {**metadata, "ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": llm2_start.isoformat(),
                "end_time": llm2_end.isoformat(),
            })
    else:
        # No tool call -- single LLM response
        llm_end = llm_start + timedelta(milliseconds=random.randint(500, 1500))
        root_end = llm_end + timedelta(milliseconds=random.randint(5, 30))

        runs.append({
            "id": llm_id,
            "trace_id": trace_id,
            "parent_run_id": root_id,
            "name": "ChatOpenAI",
            "run_type": "llm",
            "inputs": _llm_input_messages(question),
            "outputs": _llm_output_messages(response),
            "error": None,
            "extra": {"metadata": {**metadata, "ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
            "tags": tags,
            "start_time": llm_start.isoformat(),
            "end_time": llm_end.isoformat(),
        })

    # Build full conversation messages (accumulated history + this turn)
    prior = conversation_history or []
    full_messages = (
        [SYSTEM_MSG]
        + prior
        + [{"role": "user", "content": question},
           {"role": "assistant", "content": response}]
    )

    root_run = {
        "id": root_id,
        "trace_id": trace_id,
        "parent_run_id": None,
        "name": "ACME Support",
        "run_type": "chain",
        "inputs": {"question": question},
        "outputs": {
            "messages": full_messages,
            "output": response,
        },
        "error": None,
        "extra": {"metadata": metadata},
        "tags": tags,
        "start_time": root_start.isoformat(),
        "end_time": root_end.isoformat(),
    }

    return [root_run] + runs


# ---------------------------------------------------------------------------
# Thread builder
# ---------------------------------------------------------------------------
def build_thread(
    app_version: str,
    base_time: datetime,
    num_turns: int,
) -> list[dict]:
    """Build a multi-turn conversation thread (2-4 traces sharing a thread_id)."""
    thread_id = str(uuid.uuid4())
    all_runs: list[dict] = []

    is_version_b = app_version == "B"

    # Pick an opening topic
    topic = random.choice(TOPICS)
    opening_q, opening_r, opening_tool = topic

    # Fill templates
    opening_q = _fill(opening_q)
    opening_r = _fill(opening_r)

    # For Version B, decide which turns get tool errors (roughly 40% of tool calls)
    # Track which turns have tools so we can decide on errors
    turn_specs: list[tuple[str, str, str | None]] = [(opening_q, opening_r, opening_tool)]

    # Add follow-up turns
    for _ in range(num_turns - 2):  # -2 for opening + closing
        followup = random.choice(FOLLOWUPS)
        fq, fr, ftool = followup
        turn_specs.append((_fill(fq), _fill(fr), ftool))

    # Add closing turn (no tool call)
    if is_version_b:
        closing_q = random.choice(FRUSTRATED_CLOSINGS)
        closing_r = random.choice(FRUSTRATED_CLOSING_RESPONSES)
    else:
        closing_q = random.choice(POSITIVE_CLOSINGS)
        closing_r = random.choice(POSITIVE_CLOSING_RESPONSES)

    turn_specs.append((closing_q, closing_r, None))

    # Build each turn as a separate trace, accumulating conversation history
    current_time = base_time
    conversation_history: list[dict] = []  # grows each turn (excludes system msg)

    for question, response, tool_name in turn_specs:
        # Decide if this tool call should error (Version B only, ~40% of tool calls)
        tool_should_error = False
        if is_version_b and tool_name is not None:
            tool_should_error = random.random() < 0.55

        trace_runs = build_trace(
            question=question,
            response=response,
            tool_name=tool_name,
            base_time=current_time,
            app_version=app_version,
            thread_id=thread_id,
            tool_should_error=tool_should_error,
            conversation_history=list(conversation_history),
        )
        all_runs.extend(trace_runs)

        # Append this turn to history for subsequent traces
        conversation_history.append({"role": "user", "content": question})
        conversation_history.append({"role": "assistant", "content": response})

        # Time gap between turns (simulate user thinking + typing)
        # Version B has longer gaps when errors occurred (user waiting)
        if tool_should_error:
            gap_seconds = random.randint(15, 45)
        else:
            gap_seconds = random.randint(5, 20)
        current_time = current_time + timedelta(seconds=gap_seconds)

    return all_runs


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------
def generate_traces(seed: int = SEED) -> list[dict]:
    random.seed(seed)
    all_runs: list[dict] = []

    base_time = datetime(2025, 6, 15, 8, 0, 0, tzinfo=timezone.utc)

    # Version A: ~30 threads, 3-4 turns each -> ~100 traces
    for i in range(30):
        num_turns = random.choice([3, 3, 3, 4])  # mostly 3, sometimes 4
        thread_time = base_time + timedelta(
            minutes=random.randint(0, 1440),
            seconds=random.randint(0, 59),
        )
        thread_runs = build_thread(
            app_version="A",
            base_time=thread_time,
            num_turns=num_turns,
        )
        all_runs.extend(thread_runs)

    # Version B: ~30 threads, 3-4 turns each -> ~100 traces
    for i in range(30):
        num_turns = random.choice([3, 3, 3, 4])
        thread_time = base_time + timedelta(
            minutes=random.randint(0, 1440),
            seconds=random.randint(0, 59),
        )
        thread_runs = build_thread(
            app_version="B",
            base_time=thread_time,
            num_turns=num_turns,
        )
        all_runs.extend(thread_runs)

    return all_runs


def main():
    runs = generate_traces()

    # Collect stats
    trace_ids = {r["trace_id"] for r in runs}
    thread_ids = set()
    version_traces: dict[str, set] = {"A": set(), "B": set()}
    version_threads: dict[str, set] = {"A": set(), "B": set()}
    error_count = 0
    tool_count = 0

    for r in runs:
        md = (r.get("extra") or {}).get("metadata", {})
        version = md.get("app_version")
        tid = md.get("thread_id")
        if tid:
            thread_ids.add(tid)
        if version and tid:
            version_traces[version].add(r["trace_id"])
            version_threads[version].add(tid)
        if r["run_type"] == "tool":
            tool_count += 1
            if r.get("error"):
                error_count += 1

    print(f"Generated {len(runs)} runs across {len(trace_ids)} traces in {len(thread_ids)} threads")
    print(f"\nVersion A: {len(version_traces['A'])} traces, {len(version_threads['A'])} threads")
    print(f"Version B: {len(version_traces['B'])} traces, {len(version_threads['B'])} threads")
    print(f"\nTool runs: {tool_count} total, {error_count} errored ({error_count/max(tool_count,1)*100:.0f}%)")

    output_path = "module3_traces.json"
    with open(output_path, "w") as f:
        json.dump(runs, f, indent=2, default=str)
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
