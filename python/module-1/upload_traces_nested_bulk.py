"""Upload traces JSON to LangSmith with proper nested run support.

Uses batch_ingest_runs for fast bulk upload. Shifts timestamps to within
the last hour, regenerates IDs, and tags all runs with a timestamped tag.

Usage:
    uv run python upload_traces_nested_bulk.py --input 200_traces_1hr_bursty.json -p lca-temp-tracing
    uv run python upload_traces_nested_bulk.py --input traces.json -p my-project --tag my-custom-tag
"""

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client, uuid7


def parse_dt(s):
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def to_dotted_ts(dt):
    return dt.strftime('%Y%m%dT%H%M%S') + f'{dt.microsecond:06d}' + 'Z'


def main():
    parser = argparse.ArgumentParser(description="Upload traces to LangSmith (bulk)")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("-p", "--project", default="default", help="LangSmith project name")
    parser.add_argument("--tag", default=None, help="Custom tag (default: auto-generated with timestamp)")
    args = parser.parse_args()

    run_tag = args.tag or f'lca-upload-{datetime.now().strftime("%Y_%m_%d_%H%M%S")}'

    with open(args.input) as f:
        runs = json.load(f)

    print(f"Loaded {len(runs)} runs from {args.input}")
    print(f"Project: {args.project}")
    print(f"Tag: {run_tag}")

    # Shift timestamps so the latest run ends ~5 minutes ago
    latest = max(parse_dt(r["end_time"]) for r in runs if r.get("end_time"))
    shift = datetime.now(timezone.utc).replace(tzinfo=None) - latest - timedelta(minutes=5)
    print(f"Shifting timestamps by {shift}")

    # Build ID map with fresh uuid7s
    id_map = {}
    for run in runs:
        for field in ("id", "trace_id", "parent_run_id"):
            old_id = run.get(field)
            if old_id and old_id not in id_map:
                id_map[old_id] = str(uuid7())

    # Group by trace and apply transforms
    traces = defaultdict(list)
    for run in runs:
        new_start = parse_dt(run["start_time"]) + shift
        new_end = parse_dt(run["end_time"]) + shift if run.get("end_time") else None
        extra = run.get("extra") or {}
        metadata = extra.get("metadata") or {}
        if "LANGSMITH_PROJECT" in metadata:
            metadata["LANGSMITH_PROJECT"] = args.project
        traces[run["trace_id"]].append({
            "id": id_map[run["id"]],
            "trace_id": id_map[run["trace_id"]],
            "parent_run_id": id_map.get(run["parent_run_id"]),
            "name": run["name"],
            "run_type": run["run_type"],
            "inputs": run["inputs"],
            "outputs": run.get("outputs"),
            "error": run.get("error"),
            "extra": extra,
            "tags": [run_tag],
            "start_time": new_start,
            "end_time": new_end,
        })

    # Build dotted_order via BFS from root for each trace
    all_transformed = []
    for trace_runs in traces.values():
        root = [r for r in trace_runs if r["parent_run_id"] is None]
        if not root:
            continue
        root = root[0]
        root["dotted_order"] = f'{to_dotted_ts(root["start_time"])}{root["id"]}'

        children_of = defaultdict(list)
        for r in trace_runs:
            if r["parent_run_id"]:
                children_of[r["parent_run_id"]].append(r)

        queue = [root]
        while queue:
            node = queue.pop(0)
            for child in children_of.get(node["id"], []):
                child["dotted_order"] = f'{node["dotted_order"]}.{to_dotted_ts(child["start_time"])}{child["id"]}'
                queue.append(child)

        all_transformed.extend(trace_runs)

    # Build separate create and update lists for batch_ingest_runs.
    # Two-step create+update mimics native LangChain behavior so the
    # monitoring pipeline correctly indexes token/cost data.
    client = Client()
    total = len(all_transformed)
    print(f"Uploading {total} runs ({len(traces)} traces)...")

    create_list = []
    update_list = []
    for run in all_transformed:
        create_list.append({
            "id": run["id"],
            "trace_id": run["trace_id"],
            "dotted_order": run["dotted_order"],
            "parent_run_id": run["parent_run_id"],
            "name": run["name"],
            "run_type": run["run_type"],
            "inputs": run["inputs"],
            "extra": run.get("extra"),
            "tags": run["tags"],
            "start_time": run["start_time"],
            "session_name": args.project,
        })
        update_list.append({
            "id": run["id"],
            "trace_id": run["trace_id"],
            "dotted_order": run["dotted_order"],
            "parent_run_id": run["parent_run_id"],
            "extra": run.get("extra"),
            "outputs": run.get("outputs"),
            "error": run.get("error"),
            "end_time": run["end_time"],
        })

    t0 = time.time()
    batch_size = 250

    # Step 1: Send all creates
    print("Sending creates...")
    for i in range(0, total, batch_size):
        c_batch = create_list[i:i + batch_size]
        client.batch_ingest_runs(create=c_batch)
        print(f"  Created {min(i + batch_size, total)}/{total}")
    client.flush()

    # Step 2: Send all updates (outputs, end_time)
    print("Sending updates...")
    for i in range(0, total, batch_size):
        u_batch = update_list[i:i + batch_size]
        client.batch_ingest_runs(update=u_batch)
        print(f"  Updated {min(i + batch_size, total)}/{total}")
    print("Flushing...")
    client.flush()
    elapsed = time.time() - t0
    print(f"Done! Tag: {run_tag} ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
