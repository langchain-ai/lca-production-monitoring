import argparse
import asyncio
import csv
import os
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from langsmith import uuid7, Client
import uuid

from agent import Agent
from database_tool import query_database, QUERY_DATABASE_TOOL
from knowledge_base_tool import KnowledgeBase, SEARCH_KNOWLEDGE_BASE_TOOL
from csa_prompt import CSA_PROMPT_TEMPLATE, PII_VERIFICATION_SECTION
from customer_prompt import CUSTOMER_PROMPT_TEMPLATE

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PATH = str(Path(__file__).parent / "inventory" / "inventory.db")

MAX_TURNS = 20

INEXPENSIVE_MODEL = "gpt-5-nano"
POWERFUL_MODEL = "gpt-5-mini"


def load_scenarios(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def make_csa_agent(thread_store: dict[str, list], kb: KnowledgeBase, scenario: dict) -> Agent:
    reveal_pii_section = PII_VERIFICATION_SECTION if scenario.get("reveal_pii") else ""
    prompt = CSA_PROMPT_TEMPLATE.format(reveal_pii_section=reveal_pii_section)
    model = POWERFUL_MODEL if scenario.get("more_powerful_model") else INEXPENSIVE_MODEL
    return Agent(
        client=client,
        model=model,
        system_prompt=prompt,
        tools=[QUERY_DATABASE_TOOL, SEARCH_KNOWLEDGE_BASE_TOOL],
        tool_executors={
            "query_database": partial(query_database, db_path=DB_PATH),
            "search_knowledge_base": kb.search,
        },
        thread_store=thread_store,
        thread_id=str(uuid7()),
        name="Ace",
    )


def make_customer_agent(thread_store: dict[str, list], scenario: dict) -> Agent:
    prompt = CUSTOMER_PROMPT_TEMPLATE.format(**scenario)
    return Agent(
        client=client,
        model="gpt-5",
        system_prompt=prompt,
        tools=[QUERY_DATABASE_TOOL],
        tool_executors={
            "query_database": partial(query_database, db_path=DB_PATH),
        },
        thread_store=thread_store,
        thread_id=str(uuid7()),
        name=f"Customer-{scenario['fname']}",
    )


async def run_conversation(scenario: dict, kb: KnowledgeBase, run_id: str) -> list[dict]:
    """Run a single customer <-> CSA conversation until done or max turns reached."""
    thread_store: dict[str, list] = {}
    max_turns = int(scenario.get("turns", MAX_TURNS))
    conversation_id = str(uuid.uuid4())
    customer_name = f"{scenario['fname']} {scenario['lname']}"
    base_meta = {"run_id": run_id, "session_id": conversation_id, "scenario": scenario["number"], "customer_name": customer_name}
    base_tags = [customer_name, f"scenario:{scenario['number']}"]
    csa_extra = {"langsmith_extra": {"metadata": {**base_meta, "agent_name": "csa"}, "tags": [*base_tags, "csa"]}}
    customer_extra = {"langsmith_extra": {"metadata": {**base_meta, "agent_name": "customer"}, "tags": [*base_tags, "customer"]}}

    csa = make_csa_agent(thread_store, kb, scenario)
    customer = make_customer_agent(thread_store, scenario)

    label = f"[Scenario {scenario['number']}]"
    conversation: list[dict] = []
    csa_run_ids: list[str] = []

    print(f"{label} Customer starting conversation...")
    customer_result = await customer.chat("You've just connected to ACME customer support chat. Send your opening message.", **customer_extra)
    customer_message = customer_result["output"]
    conversation.append({"role": "customer", "content": customer_message})

    for turn in range(max_turns):
        print(f"{label} Turn {turn + 1}/{max_turns} — CSA responding...")
        csa_result = await csa.chat(customer_message, **csa_extra)
        csa_message = csa_result["output"]
        if csa_result.get("run_id"):
            csa_run_ids.append(csa_result["run_id"])
        conversation.append({"role": "csa", "content": csa_message})

        print(f"{label} Turn {turn + 1}/{max_turns} — Customer responding...")
        customer_result = await customer.chat(csa_message, **customer_extra)
        customer_message = customer_result["output"]
        conversation.append({"role": "customer", "content": customer_message})

        if "TASK_COMPLETE" in customer_message:
            print(f"{label} Customer satisfied — sending final message to CSA...")
            csa_result = await csa.chat(customer_message, **csa_extra)
            if csa_result.get("run_id"):
                csa_run_ids.append(csa_result["run_id"])
            conversation.append({"role": "csa", "content": csa_result["output"]})
            break

    # Add thumbs up/down feedback to all CSA traces
    satisfied = scenario.get("satisfied", "").upper() == "TRUE"
    score = 1 if satisfied else 0
    ls_client = Client()
    for rid in csa_run_ids:
        ls_client.create_feedback(run_id=rid, key="thumbs_up_down", score=score)

    return conversation


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--concurrency", type=int, default=None, help="Max concurrent conversations (default: unlimited)")
    parser.add_argument("-s", "--scenario", type=int, default=None, help="Run a single scenario by number")
    args = parser.parse_args()

    run_id = str(uuid.uuid4())
    print(f"Run ID: {run_id}")

    csv_path = str(Path(__file__).parent / "scenarios.tsv")
    scenarios = load_scenarios(csv_path)
    if args.scenario:
        scenarios = [s for s in scenarios if int(s["number"]) == args.scenario]
        if not scenarios:
            print(f"Scenario {args.scenario} not found.")
            return

    kb_dir = str(Path(__file__).parent / "knowledge_base")
    kb = KnowledgeBase(client)
    await kb.load(kb_dir)
    print()

    semaphore = asyncio.Semaphore(args.concurrency) if args.concurrency else None

    async def run_with_limit(scenario):
        if semaphore:
            async with semaphore:
                return await run_conversation(scenario, kb, run_id)
        return await run_conversation(scenario, kb, run_id)

    tasks = [run_with_limit(scenario) for scenario in scenarios]
    all_conversations = await asyncio.gather(*tasks)

    for scenario, conversation in zip(scenarios, all_conversations):
        print(f"=== Scenario {scenario['number']}: {scenario['fname']} {scenario['lname']} — {scenario['task']} ===")
        print(f"    Personality: {scenario['personality']} | Type: {scenario['query_type']} | Max turns: {scenario['turns']}")
        print()
        for msg in conversation:
            label = "Customer" if msg["role"] == "customer" else "Ace (CSA)"
            content = msg["content"].replace("TASK_COMPLETE", "").strip()
            print(f"  {label}: {content}")
            print()
        print("=" * 80)
        print()


if __name__ == "__main__":
    asyncio.run(main())
