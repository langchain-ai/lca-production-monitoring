"""
Upload capstone CSA traces to LangSmith, preserving all fields including
dotted_order, costs, and token counts.

Usage:
    uv run python upload_csa_traces.py --input capstone_traces.jsonl --project my-project
    uv run python upload_csa_traces.py --input trace_exports/rev6_csa --project my-project

Input can be:
    - A single .jsonl file (flat list of runs, one per line) — recommended
    - A directory of .jsonl files (one per trace)

The student-facing trace file is capstone_traces.jsonl in this directory.
To prepare a new version: flatten a rev directory with:
    cat trace_exports/rev<N>_csa/*.jsonl > trace_exports/rev<N>_csa/traces.jsonl
Then copy to capstone_traces.jsonl when ready for students.

Uses two-step batch_ingest_runs() create+update pattern for correct cost/token monitoring.
Timestamps are shifted to within the last 24 hours so LangSmith accepts them.
Feedback (thumbs_up_down) is applied to root runs if _feedback field is present.
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client, uuid7

BATCH_SIZE = 250


def parse_dt(s: str | None) -> datetime | None:
    if s is None:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc)


def load_runs(input_path: Path) -> list[dict]:
    runs = []
    if input_path.is_dir():
        for f in sorted(input_path.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    runs.append(json.loads(line))
    elif input_path.suffix == ".json":
        runs = json.loads(input_path.read_text())
    else:  # .jsonl flat file
        for line in input_path.read_text().splitlines():
            if line.strip():
                runs.append(json.loads(line))
    return runs


def shift_timestamps(runs: list[dict]) -> list[dict]:
    """Shift all timestamps so the latest run is ~1 hour ago."""
    times = [parse_dt(r["start_time"]) for r in runs if r.get("start_time")]
    if not times:
        return runs
    latest = max(times)
    target = datetime.now(timezone.utc) - timedelta(hours=1)
    delta = target - latest
    print(f"Shifting timestamps by: {delta}")
    for r in runs:
        if r.get("start_time"):
            r["start_time"] = (parse_dt(r["start_time"]) + delta).isoformat()
        if r.get("end_time"):
            r["end_time"] = (parse_dt(r["end_time"]) + delta).isoformat()
    return runs


def remap_ids(runs: list[dict]) -> tuple[list[dict], dict]:
    """Regenerate all run IDs while preserving relationships."""
    id_map = {}
    # Root runs first — trace_id must equal id
    for r in runs:
        if r.get("parent_run_id") is None:
            new_id = str(uuid7())
            id_map[r["id"]] = new_id
            id_map[r["trace_id"]] = new_id
    # Child runs
    for r in runs:
        if r["id"] not in id_map:
            id_map[r["id"]] = str(uuid7())
    return runs, id_map


def rebuild_dotted_order(runs: list[dict], id_map: dict) -> list[dict]:
    """Rebuild dotted_order using new IDs and shifted timestamps."""
    # Group by new trace_id
    by_trace = defaultdict(list)
    for r in runs:
        by_trace[id_map[r["trace_id"]]].append(r)

    dotted_orders = {}
    for trace_runs in by_trace.values():
        # Root first, then by start_time
        trace_runs.sort(key=lambda r: (r.get("parent_run_id") is not None, r.get("start_time") or ""))
        for r in trace_runs:
            new_id = id_map[r["id"]]
            ts = parse_dt(r["start_time"]).strftime("%Y%m%dT%H%M%S%f") + "Z"
            parent_new_id = id_map.get(r.get("parent_run_id"))
            if parent_new_id is None:
                dotted_orders[new_id] = f"{ts}{new_id}"
            else:
                parent_order = dotted_orders.get(parent_new_id, "")
                dotted_orders[new_id] = f"{parent_order}.{ts}{new_id}"
            r["_new_dotted_order"] = dotted_orders[new_id]
    return runs


def upload(runs: list[dict], id_map: dict, project: str, tag: str | None):
    client = Client()

    creates = []
    updates = []
    feedbacks = []  # (new_id, feedback_dict) for root runs with _feedback

    for r in runs:
        new_id = id_map[r["id"]]
        new_trace_id = id_map[r["trace_id"]]
        new_parent_id = id_map.get(r.get("parent_run_id"))
        dotted_order = r["_new_dotted_order"]

        tags = r.get("tags") or []
        if tag and tag not in tags:
            tags = list(tags) + [tag]

        extra = r.get("extra") or {}

        creates.append({
            "id": new_id,
            "trace_id": new_trace_id,
            "dotted_order": dotted_order,
            "parent_run_id": new_parent_id,
            "name": r.get("name"),
            "run_type": r.get("run_type"),
            "inputs": r.get("inputs") or {},
            "extra": extra,
            "tags": tags,
            "start_time": r.get("start_time"),
            "session_name": project,
        })

        updates.append({
            "id": new_id,
            "trace_id": new_trace_id,
            "dotted_order": dotted_order,
            "parent_run_id": new_parent_id,
            "extra": extra,
            "outputs": r.get("outputs"),
            "error": r.get("error"),
            "end_time": r.get("end_time"),
        })

        if r.get("_feedback") and r.get("parent_run_id") is None:
            feedbacks.append((new_id, r["_feedback"]))

    # Step 1: creates
    print(f"Uploading {len(creates)} runs in batches of {BATCH_SIZE}...")
    for i in range(0, len(creates), BATCH_SIZE):
        batch = creates[i:i + BATCH_SIZE]
        client.batch_ingest_runs(create=batch)
        print(f"  Created {min(i + BATCH_SIZE, len(creates))}/{len(creates)}")

    client.flush()
    print("Flushed creates.")

    # Step 2: updates
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        client.batch_ingest_runs(update=batch)
        print(f"  Updated {min(i + BATCH_SIZE, len(updates))}/{len(updates)}")

    client.flush()
    print("Flushed updates.")

    # Step 3: feedback
    if feedbacks:
        print(f"Adding feedback to {len(feedbacks)} root runs...")
        for new_id, fb in feedbacks:
            client.create_feedback(run_id=new_id, key=fb["key"], score=fb["score"])
        print("Feedback added.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Directory of .jsonl files or single .json/.jsonl file")
    parser.add_argument("--project", "-p", required=True, help="Target LangSmith project name")
    parser.add_argument("--tag", default=None, help="Optional extra tag to add to all traces")
    args = parser.parse_args()

    input_path = Path(args.input)
    runs = load_runs(input_path)
    print(f"Loaded {len(runs)} runs from {input_path}")

    runs = shift_timestamps(runs)
    runs, id_map = remap_ids(runs)
    runs = rebuild_dotted_order(runs, id_map)

    upload(runs, id_map, args.project, args.tag)
    print(f"\nDone. Uploaded to project '{args.project}'.")


if __name__ == "__main__":
    main()
